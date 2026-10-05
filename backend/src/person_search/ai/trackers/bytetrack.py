"""Registry-backed ByteTrack/BoT-SORT adapters with camera/job-local lifecycle state.

BoT-SORT (Ultralytics) extends ByteTrack with optional camera-motion compensation and ReID;
both are disabled here (static cameras, no extra model), so the two trackers share this
adapter and differ in their association logic only.
"""

from __future__ import annotations

import json
import math
import os
import tempfile
from collections.abc import Sequence
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path, PurePosixPath
from types import SimpleNamespace
from typing import Protocol
from uuid import UUID

from person_search.ai.registry import TrackerEntry
from person_search.storage.contracts import BoundingBoxPixels
from person_search.workers.contracts import (
    Detection,
    ModelLineage,
    SampledFrame,
    TrackState,
    TrackUpdate,
)
from person_search.workers.errors import AIErrorCode, AIWorkerError


@dataclass(frozen=True, slots=True)
class ByteTrackSettings:
    track_high_threshold: float = 0.25
    track_low_threshold: float = 0.1
    new_track_threshold: float = 0.25
    match_threshold: float = 0.8
    fuse_score: bool = True
    minimum_confirmed_samples: int = 2
    maximum_lost_samples: int = 3
    maximum_lost_milliseconds: int = 2000

    def __post_init__(self) -> None:
        thresholds = (
            self.track_high_threshold,
            self.track_low_threshold,
            self.new_track_threshold,
            self.match_threshold,
        )
        if any(
            isinstance(value, bool) or not isinstance(value, (int, float)) or not 0 <= value <= 1
            for value in thresholds
        ):
            raise ValueError("ByteTrack thresholds must be numbers between zero and one.")
        if self.track_low_threshold >= self.track_high_threshold:
            raise ValueError("track_low_threshold must be below track_high_threshold.")
        for value in (
            self.minimum_confirmed_samples,
            self.maximum_lost_samples,
            self.maximum_lost_milliseconds,
        ):
            if isinstance(value, bool) or not isinstance(value, int) or value < 1:
                raise ValueError("ByteTrack lifecycle limits must be positive integers.")


TRACKER_SCHEMAS = {"bytetrack": "bytetrack-tracker/v1", "botsort": "botsort-tracker/v1"}


def load_bytetrack_settings(
    path: str | Path, schema: str = TRACKER_SCHEMAS["bytetrack"]
) -> ByteTrackSettings:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    expected = {
        "schema_version",
        "track_high_threshold",
        "track_low_threshold",
        "new_track_threshold",
        "match_threshold",
        "fuse_score",
        "minimum_confirmed_samples",
        "maximum_lost_samples",
        "maximum_lost_milliseconds",
    }
    if not isinstance(payload, dict) or set(payload) != expected:
        raise ValueError("ByteTrack settings contain missing or unknown fields.")
    if payload.pop("schema_version") != schema:
        raise ValueError("Unsupported tracker settings schema.")
    return ByteTrackSettings(**payload)


@dataclass(frozen=True, slots=True)
class RawTrack:
    track_id: int
    x1: float
    y1: float
    x2: float
    y2: float
    detection_index: int


class ByteTrackBackend(Protocol):
    def open(self) -> None: ...

    def update(self, detections: Sequence[Detection]) -> Sequence[RawTrack]: ...

    def close(self) -> None: ...


class _Results:
    def __init__(self, xywh, confidence, classes):
        self.xywh = xywh
        self.conf = confidence
        self.cls = classes

    def __len__(self):
        return len(self.conf)

    def __getitem__(self, index):
        return _Results(self.xywh[index], self.conf[index], self.cls[index])


class UltralyticsByteTrackBackend:
    """Thin delayed-import boundary around the pinned Ultralytics ByteTrack/BoT-SORT."""

    def __init__(self, settings: ByteTrackSettings, algorithm: str = "bytetrack") -> None:
        if algorithm not in TRACKER_SCHEMAS:
            raise ValueError("Unsupported tracker algorithm.")
        self.settings = settings
        self.algorithm = algorithm
        self._tracker = None

    def open(self) -> None:
        if self._tracker is not None:
            raise RuntimeError("ByteTrack backend is already open.")
        from PIL import Image

        image_open = Image.open
        config_key = "YOLO_CONFIG_DIR"
        previous_config_dir = os.environ.get(config_key)
        if previous_config_dir is None:
            config_dir = Path(tempfile.gettempdir()) / "person-search-ultralytics"
            config_dir.mkdir(parents=True, exist_ok=True)
            os.environ[config_key] = str(config_dir)
        try:
            from ultralytics.trackers.bot_sort import BOTSORT, BOTrack
            from ultralytics.trackers.byte_tracker import BYTETracker, STrack
        finally:
            # Ultralytics patches PIL.Image.open process-wide to auto-install optional
            # HEIF support. The worker must not mutate unrelated application image I/O.
            Image.open = image_open
            if previous_config_dir is None:
                os.environ.pop(config_key, None)

        base_track = BOTrack if self.algorithm == "botsort" else STrack
        base_tracker = BOTSORT if self.algorithm == "botsort" else BYTETracker

        class LocalTrack(base_track):
            _local_count = 0

            @classmethod
            def next_id(cls) -> int:
                cls._local_count += 1
                return cls._local_count

            @classmethod
            def reset_id(cls) -> None:
                cls._local_count = 0

        class LocalByteTracker(base_tracker):
            track_class = LocalTrack

            @staticmethod
            def reset_id() -> None:
                LocalTrack.reset_id()

        args = SimpleNamespace(
            track_high_thresh=self.settings.track_high_threshold,
            track_low_thresh=self.settings.track_low_threshold,
            new_track_thresh=self.settings.new_track_threshold,
            match_thresh=self.settings.match_threshold,
            track_buffer=self.settings.maximum_lost_samples,
            fuse_score=self.settings.fuse_score,
            # BoT-SORT only: static cameras need no motion compensation; ReID stays off.
            gmc_method="none",
            proximity_thresh=0.5,
            appearance_thresh=0.8,
            with_reid=False,
            model="auto",
        )
        self._tracker = LocalByteTracker(args)

    def update(self, detections: Sequence[Detection]) -> tuple[RawTrack, ...]:
        if self._tracker is None:
            raise RuntimeError("ByteTrack backend is not open.")
        import numpy as np

        xywh = np.asarray(
            [
                [
                    item.bbox.x + item.bbox.width / 2,
                    item.bbox.y + item.bbox.height / 2,
                    item.bbox.width,
                    item.bbox.height,
                ]
                for item in detections
            ],
            dtype=np.float32,
        ).reshape((-1, 4))
        confidence = np.asarray([item.confidence for item in detections], dtype=np.float32)
        classes = np.asarray([item.class_id for item in detections], dtype=np.float32)
        rows = self._tracker.update(_Results(xywh, confidence, classes))
        return tuple(RawTrack(int(row[4]), *map(float, row[:4]), int(row[7])) for row in rows)

    def close(self) -> None:
        self._tracker = None


@dataclass(slots=True)
class _TrackRecord:
    local_track_id: str
    bbox: BoundingBoxPixels
    last_sample_sequence: int
    last_frame_index: int
    last_timestamp_ms: int
    observations: int = 1
    confirmed: bool = False


class ByteTrackPersonTracker:
    def __init__(
        self,
        backend: ByteTrackBackend,
        *,
        lineage: ModelLineage,
        settings: ByteTrackSettings,
        id_prefix: str = "bt",
    ) -> None:
        self._backend = backend
        self._id_prefix = id_prefix
        self.lineage = lineage
        self.settings = settings
        self._records: dict[int, _TrackRecord] = {}
        self._generations: dict[int, int] = {}
        self._camera_id: UUID | None = None
        self._last_sample_sequence: int | None = None
        self._opened = False
        self._closed = False

    def open(self) -> None:
        if self._opened or self._closed:
            raise RuntimeError("Tracker instances are one-shot.")
        try:
            self._backend.open()
        except Exception as exc:
            self.close()
            raise AIWorkerError(AIErrorCode.TRACKER_INFERENCE_FAILED, cause=exc) from exc
        self._opened = True

    def update(
        self, frame: SampledFrame, detections: Sequence[Detection]
    ) -> tuple[TrackUpdate, ...]:
        self._require_frame(frame)
        if any(not isinstance(item, Detection) for item in detections):
            raise TypeError("Tracker accepts Detection values only.")
        try:
            raw = tuple(self._backend.update(detections))
        except Exception as exc:
            self.close()
            raise AIWorkerError(AIErrorCode.TRACKER_INFERENCE_FAILED, cause=exc) from exc
        try:
            active = self._normalize(raw, frame, detections)
        except (TypeError, ValueError, AIWorkerError) as exc:
            self.close()
            raise AIWorkerError(AIErrorCode.TRACKER_OUTPUT_INVALID, cause=exc) from exc
        updates = list(active)
        # Include unconfirmed backend tracks as active too.  Deriving this set
        # from public local IDs is also unsafe once a backend numeric ID is
        # reused and receives a generation suffix.
        active_ids = {item.track_id for item in raw}
        for track_id, record in tuple(self._records.items()):
            if track_id in active_ids:
                continue
            sample_gap = frame.sample_sequence - record.last_sample_sequence
            time_gap = frame.source_timestamp_ms - record.last_timestamp_ms
            if (
                sample_gap > self.settings.maximum_lost_samples
                or time_gap > self.settings.maximum_lost_milliseconds
            ):
                if record.confirmed:
                    updates.append(self._track_update(track_id, record, TrackState.ENDED))
                del self._records[track_id]
        self._last_sample_sequence = frame.sample_sequence
        return tuple(updates)

    def _require_frame(self, frame: SampledFrame) -> None:
        if not self._opened or self._closed:
            raise RuntimeError("Tracker must be open before update.")
        if not isinstance(frame, SampledFrame):
            raise TypeError("Tracker accepts SampledFrame values only.")
        if self._camera_id is None:
            self._camera_id = frame.camera_id
        elif frame.camera_id != self._camera_id:
            raise ValueError("A tracker instance cannot cross camera/job boundaries.")
        if (
            self._last_sample_sequence is not None
            and frame.sample_sequence <= self._last_sample_sequence
        ):
            raise ValueError("Sample sequence must increase strictly.")

    def _normalize(
        self,
        raw: Sequence[RawTrack],
        frame: SampledFrame,
        detections: Sequence[Detection],
    ) -> tuple[TrackUpdate, ...]:
        seen: set[int] = set()
        updates = []
        for item in raw:
            if (
                not isinstance(item, RawTrack)
                or isinstance(item.track_id, bool)
                or item.track_id < 1
            ):
                raise AIWorkerError(AIErrorCode.TRACKER_OUTPUT_INVALID)
            if item.track_id in seen or not 0 <= item.detection_index < len(detections):
                raise AIWorkerError(AIErrorCode.TRACKER_OUTPUT_INVALID)
            if not all(math.isfinite(value) for value in (item.x1, item.y1, item.x2, item.y2)):
                raise AIWorkerError(AIErrorCode.TRACKER_OUTPUT_INVALID)
            seen.add(item.track_id)
            x1 = max(0, min(frame.width, math.floor(item.x1)))
            y1 = max(0, min(frame.height, math.floor(item.y1)))
            x2 = max(0, min(frame.width, math.ceil(item.x2)))
            y2 = max(0, min(frame.height, math.ceil(item.y2)))
            if x2 <= x1 or y2 <= y1:
                raise AIWorkerError(AIErrorCode.TRACKER_OUTPUT_INVALID)
            bbox = BoundingBoxPixels(x1, y1, x2 - x1, y2 - y1, frame.width, frame.height)
            record = self._records.get(item.track_id)
            if record is None:
                generation = self._generations.get(item.track_id, 0) + 1
                self._generations[item.track_id] = generation
                local_track_id = f"{self._id_prefix}-{item.track_id}"
                if generation > 1:
                    local_track_id += f"-g{generation}"
                record = _TrackRecord(
                    local_track_id,
                    bbox,
                    frame.sample_sequence,
                    frame.source_frame_index,
                    frame.source_timestamp_ms,
                )
                self._records[item.track_id] = record
            else:
                record.bbox = bbox
                record.last_sample_sequence = frame.sample_sequence
                record.last_frame_index = frame.source_frame_index
                record.last_timestamp_ms = frame.source_timestamp_ms
                record.observations += 1
            record.confirmed = record.observations >= self.settings.minimum_confirmed_samples
            if record.confirmed:
                updates.append(self._track_update(item.track_id, record, TrackState.ACTIVE))
        return tuple(updates)

    def _track_update(self, track_id: int, record: _TrackRecord, state: TrackState) -> TrackUpdate:
        assert self._camera_id is not None
        return TrackUpdate(
            local_track_id=record.local_track_id,
            camera_id=self._camera_id,
            bbox=record.bbox,
            source_frame_index=record.last_frame_index,
            source_timestamp_ms=record.last_timestamp_ms,
            state=state,
            tracker=self.lineage,
        )

    def flush(self) -> tuple[TrackUpdate, ...]:
        if not self._opened or self._closed:
            raise RuntimeError("Tracker must be open before flush.")
        updates = tuple(
            self._track_update(track_id, record, TrackState.ENDED)
            for track_id, record in sorted(self._records.items())
            if record.confirmed
        )
        self._records.clear()
        return updates

    def close(self) -> None:
        if self._closed:
            return
        self._records.clear()
        try:
            self._backend.close()
        finally:
            self._closed = True


def build_tracker(
    entry: TrackerEntry,
    *,
    artifact_root: str | Path,
    device: str = "cpu",
    backend_factory=UltralyticsByteTrackBackend,
) -> ByteTrackPersonTracker:
    """Build a registry-approved ByteTrack or BoT-SORT tracker from its verified settings file."""

    if not isinstance(entry, TrackerEntry) or entry.adapter_kind not in TRACKER_SCHEMAS:
        raise ValueError("Tracker entry is not a supported ByteTrack/BoT-SORT adapter.")
    if not entry.available:
        raise ValueError("Tracker entry is not available for production.")
    if device not in {item.value for item in entry.devices}:
        raise ValueError("Requested tracker device is not allowlisted.")
    root = Path(artifact_root).resolve()
    artifact = (root / Path(*PurePosixPath(entry.artifact.relative_path).parts)).resolve()
    if not artifact.is_relative_to(root) or not artifact.is_file():
        raise ValueError("Tracker artifact is unavailable.")
    digest = sha256(artifact.read_bytes()).hexdigest()
    if digest != entry.artifact.sha256:
        raise ValueError("Tracker artifact checksum changed.")
    settings = load_bytetrack_settings(artifact, TRACKER_SCHEMAS[entry.adapter_kind])
    if backend_factory is UltralyticsByteTrackBackend:
        backend = backend_factory(settings, entry.adapter_kind)
    else:
        backend = backend_factory(settings)
    return ByteTrackPersonTracker(
        backend,
        lineage=ModelLineage(entry.id, entry.version, entry.artifact.sha256),
        settings=settings,
        id_prefix="bs" if entry.adapter_kind == "botsort" else "bt",
    )


def build_bytetrack(
    entry: TrackerEntry,
    *,
    artifact_root: str | Path,
    device: str = "cpu",
    backend_factory=UltralyticsByteTrackBackend,
) -> ByteTrackPersonTracker:
    if not isinstance(entry, TrackerEntry) or entry.adapter_kind != "bytetrack":
        raise ValueError("Tracker entry is not a ByteTrack adapter.")
    return build_tracker(
        entry, artifact_root=artifact_root, device=device, backend_factory=backend_factory
    )
