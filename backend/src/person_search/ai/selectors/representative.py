"""Deterministic bounded best-shot selector with shared full-frame ownership."""

from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from pathlib import Path
from uuid import UUID

from PIL import Image, ImageFilter, ImageStat

from person_search.storage.contracts import BoundingBoxPixels
from person_search.workers.contracts import (
    CompletedTrack,
    ModelLineage,
    QualityComponent,
    QualityFlag,
    RepresentativeCandidate,
    SampledFrame,
    SourceFrame,
    TrackState,
    TrackUpdate,
)
from person_search.workers.errors import AIErrorCode, AIWorkerError


@dataclass(frozen=True, slots=True)
class SelectorSettings:
    max_candidates_per_track: int = 3
    max_buffer_bytes: int = 256 * 1024 * 1024
    minimum_bbox_width: int = 24
    minimum_bbox_height: int = 48
    minimum_sharpness_variance: float = 15.0
    sharpness_reference_variance: float = 250.0
    severe_border_contacts: int = 2
    maximum_area_change_ratio: float = 4.0
    maximum_aspect_change_ratio: float = 2.5
    border_penalty_per_contact: float = 0.1
    maximum_occlusion_penalty: float = 0.2
    crop_padding_ratio: float = 0.05

    def __post_init__(self) -> None:
        integers = (
            self.max_candidates_per_track,
            self.max_buffer_bytes,
            self.minimum_bbox_width,
            self.minimum_bbox_height,
            self.severe_border_contacts,
        )
        if any(
            isinstance(value, bool) or not isinstance(value, int) or value < 1
            for value in integers
        ):
            raise ValueError("Selector integer limits must be positive integers.")
        positives = (
            self.minimum_sharpness_variance,
            self.sharpness_reference_variance,
            self.maximum_area_change_ratio,
            self.maximum_aspect_change_ratio,
        )
        if any(
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not math.isfinite(value)
            or value <= 0
            for value in positives
        ):
            raise ValueError("Selector thresholds must be positive finite numbers.")
        fractions = (
            self.border_penalty_per_contact,
            self.maximum_occlusion_penalty,
            self.crop_padding_ratio,
        )
        if any(
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not 0 <= value <= 1
            for value in fractions
        ):
            raise ValueError("Selector penalties and padding must be between zero and one.")


def load_selector_settings(path: str | Path) -> SelectorSettings:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    expected = {"schema_version", *SelectorSettings.__dataclass_fields__}
    if not isinstance(payload, dict) or set(payload) != expected:
        raise ValueError("Representative selector settings contain missing or unknown fields.")
    if payload.pop("schema_version") != "representative-selector/v1":
        raise ValueError("Unsupported representative selector settings schema.")
    return SelectorSettings(**payload)


@dataclass(frozen=True, slots=True)
class SelectorMetrics:
    buffered_bytes: int
    buffered_frames: int
    buffered_candidates: int
    evicted_candidates: int


@dataclass(slots=True)
class _SharedFrame:
    frame: SourceFrame
    size_bytes: int
    references: int = 0


@dataclass(slots=True)
class _Candidate:
    frame_key: tuple[UUID, int]
    bbox: BoundingBoxPixels
    resolution: float
    sharpness: float
    completeness: float
    stability: float
    border_penalty: float
    hard_filter_passed: bool
    occlusion_penalty: float = 0.0


@dataclass(slots=True)
class _TrackRecord:
    camera_id: UUID
    local_track_id: str
    started_at_ms: int
    ended_at_ms: int
    sampling_interval: int
    tracker: ModelLineage
    candidates: list[_Candidate] = field(default_factory=list)
    previous_bbox: BoundingBoxPixels | None = None


class RepresentativeFrameSelector:
    """Retain at most K full-frame candidates per track under one byte budget."""

    def __init__(
        self,
        *,
        processing_job_id: UUID,
        ai_config_version_id: UUID,
        detector: ModelLineage,
        tracker: ModelLineage,
        encoder: ModelLineage,
        settings: SelectorSettings | None = None,
    ) -> None:
        self.processing_job_id = processing_job_id
        self.ai_config_version_id = ai_config_version_id
        self.detector = detector
        self.tracker = tracker
        self.encoder = encoder
        self.settings = settings or SelectorSettings()
        self._tracks: dict[str, _TrackRecord] = {}
        self._frames: dict[tuple[UUID, int], _SharedFrame] = {}
        self._completed: list[CompletedTrack] = []
        self._completed_images: list[Image.Image] = []
        self._transferred_frames: set[tuple[UUID, int]] = set()
        self._buffered_bytes = 0
        self._evicted = 0
        self._opened = False
        self._closed = False

    @property
    def metrics(self) -> SelectorMetrics:
        return SelectorMetrics(
            self._buffered_bytes,
            len(self._frames),
            sum(len(record.candidates) for record in self._tracks.values()),
            self._evicted,
        )

    def open(self) -> None:
        if self._opened or self._closed:
            raise RuntimeError("Selector instances are one-shot.")
        self._opened = True

    def consider(self, frame: SampledFrame, update: TrackUpdate) -> None:
        if not self._opened or self._closed:
            raise RuntimeError("Selector must be open before considering tracks.")
        if not isinstance(frame, SampledFrame) or not isinstance(update, TrackUpdate):
            raise TypeError("Selector requires SampledFrame and TrackUpdate values.")
        if frame.camera_id != update.camera_id:
            raise ValueError("Track update and frame must belong to the same camera.")
        if update.tracker != self.tracker:
            raise ValueError("Track update lineage does not match the configured tracker.")
        if update.state is TrackState.ENDED:
            record = self._tracks.get(update.local_track_id)
            if record is None:
                return
            record.ended_at_ms = update.source_timestamp_ms
            self._finalize(update.local_track_id)
            return
        if (
            update.source_frame_index != frame.source_frame_index
            or update.source_timestamp_ms != frame.source_timestamp_ms
        ):
            raise ValueError("Active track update must reference the supplied sampled frame.")
        record = self._tracks.get(update.local_track_id)
        if record is None:
            record = _TrackRecord(
                frame.camera_id,
                update.local_track_id,
                frame.source_timestamp_ms,
                frame.source_timestamp_ms,
                frame.sampling_interval,
                update.tracker,
            )
            self._tracks[update.local_track_id] = record
        elif record.camera_id != frame.camera_id:
            raise ValueError("A local track cannot cross camera boundaries.")
        elif frame.source_timestamp_ms < record.ended_at_ms:
            raise ValueError("Track timestamps must not decrease.")
        record.ended_at_ms = frame.source_timestamp_ms
        candidate = self._candidate(frame, update.bbox, record.previous_bbox)
        record.previous_bbox = update.bbox
        self._retain(record, frame.source, candidate)

    def _candidate(
        self,
        frame: SampledFrame,
        bbox: BoundingBoxPixels,
        previous: BoundingBoxPixels | None,
    ) -> _Candidate:
        area = bbox.width * bbox.height
        frame_area = frame.width * frame.height
        resolution = min(1.0, math.sqrt(area / max(1.0, frame_area * 0.15)))
        crop = frame.image.crop((bbox.x, bbox.y, bbox.x + bbox.width, bbox.y + bbox.height))
        try:
            variance = ImageStat.Stat(crop.convert("L").filter(ImageFilter.FIND_EDGES)).var[0]
        finally:
            crop.close()
        sharpness = min(1.0, variance / self.settings.sharpness_reference_variance)
        contacts = sum(
            (
                bbox.x == 0,
                bbox.y == 0,
                bbox.x + bbox.width == frame.width,
                bbox.y + bbox.height == frame.height,
            )
        )
        ratio = bbox.width / bbox.height
        completeness = max(0.0, 1.0 - abs(ratio - 0.42) / 0.84 - contacts * 0.15)
        stability = 0.5 if previous is None else _bbox_iou(previous, bbox)
        stable_shape = True
        if previous is not None:
            previous_area = previous.width * previous.height
            area_change = max(area, previous_area) / min(area, previous_area)
            previous_ratio = previous.width / previous.height
            aspect_change = max(ratio, previous_ratio) / min(ratio, previous_ratio)
            stable_shape = (
                area_change <= self.settings.maximum_area_change_ratio
                and aspect_change <= self.settings.maximum_aspect_change_ratio
            )
        hard_filter_passed = (
            bbox.width >= self.settings.minimum_bbox_width
            and bbox.height >= self.settings.minimum_bbox_height
            and variance >= self.settings.minimum_sharpness_variance
            and contacts < self.settings.severe_border_contacts
            and stable_shape
        )
        return _Candidate(
            (frame.camera_id, frame.source_frame_index),
            bbox,
            resolution,
            sharpness,
            completeness,
            stability,
            contacts * self.settings.border_penalty_per_contact,
            hard_filter_passed,
        )

    def _retain(
        self, record: _TrackRecord, source: SourceFrame, candidate: _Candidate
    ) -> None:
        size = source.width * source.height * 3
        if size > self.settings.max_buffer_bytes:
            raise AIWorkerError(AIErrorCode.RESOURCE_EXHAUSTED)
        shared = self._frames.get(candidate.frame_key)
        if shared is None:
            image = source.image.copy()
            owned = SourceFrame(
                source.camera_id,
                source.source_frame_index,
                source.source_timestamp_ms,
                image,
                source.width,
                source.height,
            )
            shared = _SharedFrame(owned, size)
            self._frames[candidate.frame_key] = shared
            self._buffered_bytes += size
        elif (
            shared.frame.source_timestamp_ms != source.source_timestamp_ms
            or shared.frame.image.size != source.image.size
        ):
            raise ValueError("A source frame identity was reused with different content metadata.")
        shared.references += 1
        record.candidates.append(candidate)
        self._refresh_occlusion(candidate.frame_key)
        while len(record.candidates) > self.settings.max_candidates_per_track:
            self._evict(min(record.candidates, key=lambda item: self._rank(item, record)))
        while self._buffered_bytes > self.settings.max_buffer_bytes:
            candidates = [
                item
                for item_record in self._tracks.values()
                for item in item_record.candidates
            ]
            if not candidates:
                raise AIWorkerError(AIErrorCode.RESOURCE_EXHAUSTED)
            self._evict(min(candidates, key=self._global_rank))

    def _rank(self, candidate: _Candidate, record: _TrackRecord) -> tuple[float, ...]:
        quality, _ = self._score(candidate, record)
        return (quality, candidate.sharpness, candidate.resolution, -candidate.frame_key[1])

    def _global_rank(self, candidate: _Candidate) -> tuple[float, ...]:
        record = next(
            record
            for record in self._tracks.values()
            if any(item is candidate for item in record.candidates)
        )
        return self._rank(candidate, record)

    def _score(
        self, candidate: _Candidate, record: _TrackRecord
    ) -> tuple[float, tuple[QualityComponent, ...]]:
        shared = self._frames[candidate.frame_key]
        duration = record.ended_at_ms - record.started_at_ms
        if duration <= 0:
            temporal = 0.5
        else:
            position = (shared.frame.source_timestamp_ms - record.started_at_ms) / duration
            temporal = max(0.0, 1.0 - 2.0 * abs(position - 0.5))
        occlusion = candidate.occlusion_penalty
        quality = (
            0.30 * candidate.resolution
            + 0.25 * candidate.sharpness
            + 0.20 * candidate.completeness
            + 0.15 * candidate.stability
            + 0.10 * temporal
            - candidate.border_penalty
            - occlusion
        )
        components = (
            QualityComponent("person_resolution", candidate.resolution),
            QualityComponent("sharpness", candidate.sharpness),
            QualityComponent("body_completeness", candidate.completeness),
            QualityComponent("detection_track_stability", candidate.stability),
            QualityComponent("temporal_preference", temporal),
            QualityComponent("border_clipping_penalty", candidate.border_penalty),
            QualityComponent("occlusion_penalty", occlusion),
        )
        return quality, components

    def _refresh_occlusion(self, frame_key: tuple[UUID, int]) -> None:
        candidates = [
            candidate
            for record in self._tracks.values()
            for candidate in record.candidates
            if candidate.frame_key == frame_key
        ]
        for candidate in candidates:
            overlaps = [
                _bbox_iou(candidate.bbox, other.bbox)
                for other in candidates
                if other is not candidate
            ]
            candidate.occlusion_penalty = (
                (max(overlaps) if overlaps else 0.0)
                * self.settings.maximum_occlusion_penalty
            )

    def _evict(self, candidate: _Candidate) -> None:
        for record in self._tracks.values():
            for index, item in enumerate(record.candidates):
                if item is not candidate:
                    continue
                record.candidates.pop(index)
                self._release(candidate, close=True)
                self._refresh_occlusion(candidate.frame_key)
                self._evicted += 1
                return

    def _release(self, candidate: _Candidate, *, close: bool) -> None:
        shared = self._frames[candidate.frame_key]
        shared.references -= 1
        if shared.references == 0:
            self._buffered_bytes -= shared.size_bytes
            del self._frames[candidate.frame_key]
            if close and candidate.frame_key not in self._transferred_frames:
                shared.frame.image.close()

    def _finalize(self, local_track_id: str) -> None:
        record = self._tracks.pop(local_track_id)
        if not record.candidates:
            raise AIWorkerError(AIErrorCode.SELECTOR_NO_REPRESENTATIVE)
        accepted = [item for item in record.candidates if item.hard_filter_passed]
        pool = accepted or record.candidates
        selected = max(pool, key=lambda item: self._rank(item, record))
        quality, components = self._score(selected, record)
        frame = self._frames[selected.frame_key].frame
        representative = RepresentativeCandidate(frame, selected.bbox, components, quality)
        self._completed.append(
            CompletedTrack(
                record.camera_id,
                self.processing_job_id,
                self.ai_config_version_id,
                record.local_track_id,
                record.started_at_ms,
                record.ended_at_ms,
                representative,
                QualityFlag.ACCEPTED if accepted else QualityFlag.LOW_QUALITY,
                record.sampling_interval,
                self.detector,
                record.tracker,
                self.encoder,
            )
        )
        self._completed_images.append(frame.image)
        self._transferred_frames.add(selected.frame_key)
        for candidate in tuple(record.candidates):
            self._release(candidate, close=candidate is not selected)

    def flush(self) -> tuple[CompletedTrack, ...]:
        if not self._opened or self._closed:
            raise RuntimeError("Selector must be open before flush.")
        for local_track_id in tuple(self._tracks):
            self._finalize(local_track_id)
        completed = tuple(self._completed)
        self._completed.clear()
        self._completed_images.clear()
        self._transferred_frames.clear()
        return completed

    def close(self) -> None:
        if self._closed:
            return
        for shared in self._frames.values():
            shared.frame.image.close()
        for image in self._completed_images:
            image.close()
        self._frames.clear()
        self._tracks.clear()
        self._completed.clear()
        self._completed_images.clear()
        self._transferred_frames.clear()
        self._buffered_bytes = 0
        self._closed = True


def crop_representative(
    candidate: RepresentativeCandidate, *, padding_ratio: float = 0.05
) -> Image.Image:
    if not 0 <= padding_ratio <= 1:
        raise ValueError("padding_ratio must be between zero and one.")
    bbox = candidate.bbox
    padding_x = round(bbox.width * padding_ratio)
    padding_y = round(bbox.height * padding_ratio)
    left = max(0, bbox.x - padding_x)
    top = max(0, bbox.y - padding_y)
    right = min(bbox.frame_width, bbox.x + bbox.width + padding_x)
    bottom = min(bbox.frame_height, bbox.y + bbox.height + padding_y)
    return candidate.frame.image.crop((left, top, right, bottom))


def _bbox_iou(first: BoundingBoxPixels, second: BoundingBoxPixels) -> float:
    left = max(first.x, second.x)
    top = max(first.y, second.y)
    right = min(first.x + first.width, second.x + second.width)
    bottom = min(first.y + first.height, second.y + second.height)
    intersection = max(0, right - left) * max(0, bottom - top)
    union = first.width * first.height + second.width * second.height - intersection
    return intersection / union if union else 0.0
