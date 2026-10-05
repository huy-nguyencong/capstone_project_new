"""Production source-to-embedding pipeline assembled from registry-approved adapters."""

from __future__ import annotations

import time
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol
from uuid import UUID

from person_search.ai.detectors import build_yolo_detector, load_detector_settings
from person_search.ai.encoders import (
    RasaTrackImageEncoder,
    build_rasa_image_encoder,
    load_rasa_settings,
)
from person_search.ai.registry import ModelRegistry
from person_search.ai.selectors import RepresentativeFrameSelector, load_selector_settings
from person_search.ai.trackers import build_tracker
from person_search.workers.contracts import (
    CompletedTrack,
    EmbeddingVector,
    ModelLineage,
    SourceFrame,
)
from person_search.workers.errors import AIErrorCode, AIWorkerError
from person_search.workers.sampling import FrameSampler


class Cancellable(Protocol):
    def __call__(self) -> bool: ...


class ProgressObserver(Protocol):
    def __call__(self, source_frames: int, sampled_frames: int, completed_tracks: int) -> None: ...


@dataclass(frozen=True, slots=True)
class EncodedTrack:
    track: CompletedTrack
    embedding: EmbeddingVector

    def __post_init__(self) -> None:
        if not isinstance(self.track, CompletedTrack):
            raise ValueError("track must be a CompletedTrack value.")
        if not isinstance(self.embedding, EmbeddingVector):
            raise ValueError("embedding must be an EmbeddingVector value.")
        if self.track.encoder != self.embedding.encoder:
            raise ValueError("Track and embedding encoder lineage must match.")


@dataclass(frozen=True, slots=True)
class StageTiming:
    stage: str
    calls: int
    elapsed_ms: float


@dataclass(frozen=True, slots=True)
class ProductionPipelineResult:
    source_frames: int
    sampled_frames: int
    detections: int
    track_updates: int
    encoded_tracks: tuple[EncodedTrack, ...]
    timings: tuple[StageTiming, ...]


class ProductionPipeline:
    """Synchronous bounded pipeline; publication and durable jobs remain downstream tasks."""

    def __init__(
        self,
        detector,
        tracker,
        selector: RepresentativeFrameSelector,
        image_encoder,
        *,
        sampling_interval: int,
        job_timeout_seconds: float,
        cancelled: Cancellable = lambda: False,
        progress: ProgressObserver = lambda *_: None,
        clock: Callable[[], float] = time.perf_counter,
    ) -> None:
        if isinstance(job_timeout_seconds, bool) or job_timeout_seconds <= 0:
            raise ValueError("job_timeout_seconds must be positive.")
        self.detector = detector
        self.tracker = tracker
        self.selector = selector
        self.image_encoder = image_encoder
        self.track_encoder = RasaTrackImageEncoder(image_encoder)
        self.sampler = FrameSampler(sampling_interval)
        self.job_timeout_seconds = float(job_timeout_seconds)
        self.cancelled = cancelled
        self.progress = progress
        self.clock = clock
        self._timings: dict[str, list[float | int]] = {}

    def _check(self, started: float) -> None:
        if self.cancelled():
            raise AIWorkerError(AIErrorCode.CANCELLED)
        if self.clock() - started > self.job_timeout_seconds:
            raise AIWorkerError(
                AIErrorCode.RESOURCE_EXHAUSTED,
                internal_detail="Production pipeline exceeded its job deadline.",
            )

    def _call(self, stage: str, function, *args):
        started = self.clock()
        try:
            return function(*args)
        finally:
            elapsed = max(0.0, (self.clock() - started) * 1000)
            values = self._timings.setdefault(stage, [0, 0.0])
            values[0] += 1
            values[1] += elapsed

    def stage_timings(self) -> tuple[StageTiming, ...]:
        return tuple(
            StageTiming(name, int(values[0]), float(values[1]))
            for name, values in self._timings.items()
        )

    def run(self, frames: Iterable[SourceFrame]) -> ProductionPipelineResult:
        started = self.clock()
        source_count = sampled_count = detection_count = update_count = 0
        encoded: list[EncodedTrack] = []
        completed: tuple[CompletedTrack, ...] = ()
        opened = []
        succeeded = False
        try:
            for component in (
                self.detector,
                self.tracker,
                self.selector,
                self.image_encoder,
            ):
                self._call("load", component.open)
                opened.append(component)
            for frame in frames:
                if not isinstance(frame, SourceFrame):
                    raise AIWorkerError(AIErrorCode.SOURCE_INVALID_FRAME)
                try:
                    self._check(started)
                    source_count += 1
                    sampled = self._call("sampling", self.sampler.sample, frame)
                    if sampled is None:
                        continue
                    sampled_count += 1
                    detections = tuple(self._call("detector", self.detector.detect, sampled))
                    detection_count += len(detections)
                    updates = tuple(self._call("tracker", self.tracker.update, sampled, detections))
                    update_count += len(updates)
                    for update in updates:
                        self._call("selector", self.selector.consider, sampled, update)
                    self._check(started)
                finally:
                    frame.image.close()
                self.progress(source_count, sampled_count, len(encoded))
            ended = tuple(self._call("tracker", self.tracker.flush))
            update_count += len(ended)
            # ENDED updates do not inspect the supplied frame; they only finalize retained state.
            if ended:
                sentinel = self._sentinel_for_ended(ended)
                try:
                    for update in ended:
                        self._call("selector", self.selector.consider, sentinel, update)
                finally:
                    sentinel.source.image.close()
            completed = tuple(self._call("selector", self.selector.flush))
            for track in completed:
                self._check(started)
                embedding = self._call("image_encoder", self.track_encoder.encode, track)
                encoded.append(EncodedTrack(track, embedding))
                self.progress(source_count, sampled_count, len(encoded))
            succeeded = True
            return ProductionPipelineResult(
                source_count,
                sampled_count,
                detection_count,
                update_count,
                tuple(encoded),
                self.stage_timings(),
            )
        finally:
            for component in reversed(opened):
                component.close()
            if not succeeded:
                images = {
                    id(item.representative.frame.image): item.representative.frame.image
                    for item in completed
                }
                for image in images.values():
                    image.close()

    def _sentinel_for_ended(self, ended):
        from PIL import Image

        from person_search.workers.contracts import SampledFrame

        first = ended[0]
        image = Image.new("RGB", (1, 1))
        source = SourceFrame(
            first.camera_id,
            first.source_frame_index,
            first.source_timestamp_ms,
            image,
            1,
            1,
        )
        return SampledFrame(source, 1, first.source_frame_index)


def build_production_pipeline(
    registry: ModelRegistry,
    config,
    *,
    artifact_root: str | Path,
    detector_settings_path: str | Path,
    selector_settings_path: str | Path,
    rasa_settings_path: str | Path,
    processing_job_id: UUID,
    ai_config_version_id: UUID,
    sampling_interval: int,
    job_timeout_seconds: float,
    device: str = "cpu",
    cancelled: Cancellable = lambda: False,
    progress: ProgressObserver = lambda *_: None,
    selection=None,
) -> ProductionPipeline:
    """Resolve immutable config through the registry; never substitute demo adapters."""

    selection = selection or registry.resolve_config(config)
    detector = build_yolo_detector(
        selection.detector,
        artifact_root=artifact_root,
        device=device,
        settings=load_detector_settings(detector_settings_path),
    )
    tracker = build_tracker(
        selection.tracker,
        artifact_root=artifact_root,
        device=device,
    )
    lineage = ModelLineage(
        selection.encoder.id,
        selection.encoder.version,
        selection.encoder.artifact.sha256,
    )
    selector = RepresentativeFrameSelector(
        processing_job_id=processing_job_id,
        ai_config_version_id=ai_config_version_id,
        detector=detector.lineage,
        tracker=tracker.lineage,
        encoder=lineage,
        settings=load_selector_settings(selector_settings_path),
    )
    encoder = build_rasa_image_encoder(
        selection.encoder,
        artifact_root=artifact_root,
        runtime_settings=load_rasa_settings(rasa_settings_path),
        device=device,
    )
    return ProductionPipeline(
        detector,
        tracker,
        selector,
        encoder,
        sampling_interval=sampling_interval,
        job_timeout_seconds=job_timeout_seconds,
        cancelled=cancelled,
        progress=progress,
    )
