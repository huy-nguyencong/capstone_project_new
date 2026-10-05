"""Framework-neutral contracts shared by AI worker components.

The objects in this module are deliberately independent from a concrete detector,
tracker, encoder, decoder, or storage SDK.  Boundary validation happens here so
orchestration code can rely on one set of invariants.
"""

from __future__ import annotations

import math
from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import StrEnum
from pathlib import Path
from typing import Any, Protocol, Self, runtime_checkable
from uuid import UUID

from PIL import Image

from person_search.storage.contracts import BoundingBoxPixels


def _require_int(value: object, field_name: str, *, minimum: int = 0) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise ValueError(f"{field_name} must be an integer greater than or equal to {minimum}.")
    return value


def _require_nonempty(value: object, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be a non-empty string.")
    return value


def _require_uuid(value: object, field_name: str) -> UUID:
    if not isinstance(value, UUID):
        raise ValueError(f"{field_name} must be a UUID value.")
    return value


def _require_sha256(value: object, field_name: str) -> str:
    text = _require_nonempty(value, field_name).lower()
    if len(text) != 64 or any(character not in "0123456789abcdef" for character in text):
        raise ValueError(f"{field_name} must contain exactly 64 hexadecimal characters.")
    return text


def _require_finite(value: object, field_name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{field_name} must be a finite number.")
    result = float(value)
    if not math.isfinite(result):
        raise ValueError(f"{field_name} must be a finite number.")
    return result


def _require_utc(value: object, field_name: str) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() != timedelta(0):
        raise ValueError(f"{field_name} must be timezone-aware and normalized to UTC.")
    return value


@dataclass(frozen=True, slots=True)
class ModelLineage:
    """Identity of one registry-managed component artifact."""

    registry_id: str
    version: str
    artifact_sha256: str

    def __post_init__(self) -> None:
        _require_nonempty(self.registry_id, "registry_id")
        _require_nonempty(self.version, "version")
        object.__setattr__(
            self,
            "artifact_sha256",
            _require_sha256(self.artifact_sha256, "artifact_sha256"),
        )


class SourceKind(StrEnum):
    FILE = "FILE"
    RTSP = "RTSP"


class PixelColorSpace(StrEnum):
    RGB = "RGB"


@dataclass(frozen=True, slots=True)
class FrameSourceMetadata:
    """Non-secret source properties exposed uniformly after a source is opened."""

    kind: SourceKind
    camera_id: UUID
    color_space: PixelColorSpace = PixelColorSpace.RGB
    orientation_normalized: bool = True

    def __post_init__(self) -> None:
        if not isinstance(self.kind, SourceKind):
            raise ValueError("kind must be a SourceKind value.")
        _require_uuid(self.camera_id, "camera_id")
        if self.color_space is not PixelColorSpace.RGB:
            raise ValueError("Frame sources must expose RGB pixels.")
        if self.orientation_normalized is not True:
            raise ValueError("Frame sources must normalize image orientation.")


@dataclass(frozen=True, slots=True)
class SourceFrame:
    """One decoded source frame with source-derived position and timestamp."""

    camera_id: UUID
    source_frame_index: int
    source_timestamp_ms: int
    image: Image.Image
    width: int
    height: int

    def __post_init__(self) -> None:
        _require_uuid(self.camera_id, "camera_id")
        _require_int(self.source_frame_index, "source_frame_index")
        _require_int(self.source_timestamp_ms, "source_timestamp_ms")
        _require_int(self.width, "width", minimum=1)
        _require_int(self.height, "height", minimum=1)
        if not isinstance(self.image, Image.Image):
            raise ValueError("image must be a PIL image.")
        if self.image.mode != PixelColorSpace.RGB.value:
            raise ValueError("image must use RGB color space.")
        if self.image.size != (self.width, self.height):
            raise ValueError("width and height must match the decoded image dimensions.")

    @property
    def index(self) -> int:
        """Compatibility alias while the legacy worker is migrated."""

        return self.source_frame_index

    @property
    def timestamp_ms(self) -> int:
        """Compatibility alias while the legacy worker is migrated."""

        return self.source_timestamp_ms


@dataclass(frozen=True, slots=True)
class SampledFrame:
    """A source frame selected before Detector and Tracker inference."""

    source: SourceFrame
    sampling_interval: int
    sample_sequence: int

    def __post_init__(self) -> None:
        if not isinstance(self.source, SourceFrame):
            raise ValueError("source must be a SourceFrame value.")
        _require_int(self.sampling_interval, "sampling_interval", minimum=1)
        _require_int(self.sample_sequence, "sample_sequence")
        expected_index = self.sample_sequence * self.sampling_interval
        if self.source.source_frame_index != expected_index:
            raise ValueError("Sample sequence must map exactly to the source frame index.")

    @property
    def image(self) -> Image.Image:
        return self.source.image

    @property
    def camera_id(self) -> UUID:
        return self.source.camera_id

    @property
    def source_frame_index(self) -> int:
        return self.source.source_frame_index

    @property
    def source_timestamp_ms(self) -> int:
        return self.source.source_timestamp_ms

    @property
    def index(self) -> int:
        return self.source_frame_index

    @property
    def timestamp_ms(self) -> int:
        return self.source_timestamp_ms

    @property
    def width(self) -> int:
        return self.source.width

    @property
    def height(self) -> int:
        return self.source.height


@dataclass(frozen=True, slots=True)
class Detection:
    """One normalized person detection in original-frame pixel coordinates."""

    bbox: BoundingBoxPixels
    class_id: int
    class_name: str
    confidence: float
    detector: ModelLineage

    def __post_init__(self) -> None:
        if not isinstance(self.bbox, BoundingBoxPixels):
            raise ValueError("bbox must be a BoundingBoxPixels value.")
        _require_int(self.class_id, "class_id")
        if self.class_name != "person":
            raise ValueError("Only the normalized person class may cross the detector boundary.")
        confidence = _require_finite(self.confidence, "confidence")
        if not 0.0 <= confidence <= 1.0:
            raise ValueError("confidence must be between 0 and 1.")
        object.__setattr__(self, "confidence", confidence)
        if not isinstance(self.detector, ModelLineage):
            raise ValueError("detector must be a ModelLineage value.")


class TrackState(StrEnum):
    ACTIVE = "ACTIVE"
    ENDED = "ENDED"


@dataclass(frozen=True, slots=True)
class TrackUpdate:
    """Tracker output for one local, camera-scoped track at one sampled frame."""

    local_track_id: str
    camera_id: UUID
    bbox: BoundingBoxPixels
    source_frame_index: int
    source_timestamp_ms: int
    state: TrackState
    tracker: ModelLineage

    def __post_init__(self) -> None:
        _require_nonempty(self.local_track_id, "local_track_id")
        _require_uuid(self.camera_id, "camera_id")
        if not isinstance(self.bbox, BoundingBoxPixels):
            raise ValueError("bbox must be a BoundingBoxPixels value.")
        _require_int(self.source_frame_index, "source_frame_index")
        _require_int(self.source_timestamp_ms, "source_timestamp_ms")
        if not isinstance(self.state, TrackState):
            raise ValueError("state must be a TrackState value.")
        if not isinstance(self.tracker, ModelLineage):
            raise ValueError("tracker must be a ModelLineage value.")


@dataclass(frozen=True, slots=True)
class QualityComponent:
    name: str
    value: float

    def __post_init__(self) -> None:
        _require_nonempty(self.name, "quality component name")
        object.__setattr__(self, "value", _require_finite(self.value, "quality value"))


@dataclass(frozen=True, slots=True)
class RepresentativeCandidate:
    """Transient full-frame candidate considered by the best-shot selector."""

    frame: SourceFrame
    bbox: BoundingBoxPixels
    quality_components: tuple[QualityComponent, ...]
    total_quality: float

    def __post_init__(self) -> None:
        if not isinstance(self.frame, SourceFrame):
            raise ValueError("frame must be a SourceFrame value.")
        if not isinstance(self.bbox, BoundingBoxPixels):
            raise ValueError("bbox must be a BoundingBoxPixels value.")
        if (self.bbox.frame_width, self.bbox.frame_height) != (
            self.frame.width,
            self.frame.height,
        ):
            raise ValueError("bbox frame dimensions must match the representative frame.")
        components = tuple(self.quality_components)
        if not components or not all(isinstance(item, QualityComponent) for item in components):
            raise ValueError("quality_components must contain QualityComponent values.")
        if len({item.name for item in components}) != len(components):
            raise ValueError("quality component names must be unique.")
        object.__setattr__(self, "quality_components", components)
        object.__setattr__(
            self, "total_quality", _require_finite(self.total_quality, "total_quality")
        )


class QualityFlag(StrEnum):
    ACCEPTED = "ACCEPTED"
    LOW_QUALITY = "LOW_QUALITY"


@dataclass(frozen=True, slots=True)
class CompletedTrack:
    """Complete track ready for transient crop encoding and publication."""

    camera_id: UUID
    processing_job_id: UUID
    ai_config_version_id: UUID
    local_track_id: str
    source_started_at_ms: int
    source_ended_at_ms: int
    representative: RepresentativeCandidate
    quality_flag: QualityFlag
    sampling_interval: int
    detector: ModelLineage
    tracker: ModelLineage
    encoder: ModelLineage

    def __post_init__(self) -> None:
        _require_uuid(self.camera_id, "camera_id")
        _require_uuid(self.processing_job_id, "processing_job_id")
        _require_uuid(self.ai_config_version_id, "ai_config_version_id")
        _require_nonempty(self.local_track_id, "local_track_id")
        start = _require_int(self.source_started_at_ms, "source_started_at_ms")
        end = _require_int(self.source_ended_at_ms, "source_ended_at_ms")
        if end < start:
            raise ValueError("source_ended_at_ms must not precede source_started_at_ms.")
        if not isinstance(self.representative, RepresentativeCandidate):
            raise ValueError("representative must be a RepresentativeCandidate value.")
        timestamp = self.representative.frame.source_timestamp_ms
        if not start <= timestamp <= end:
            raise ValueError("Representative timestamp must be inside the track interval.")
        if self.representative.frame.camera_id != self.camera_id:
            raise ValueError("Representative frame must belong to the track camera.")
        if not isinstance(self.quality_flag, QualityFlag):
            raise ValueError("quality_flag must be a QualityFlag value.")
        _require_int(self.sampling_interval, "sampling_interval", minimum=1)
        for name in ("detector", "tracker", "encoder"):
            if not isinstance(getattr(self, name), ModelLineage):
                raise ValueError(f"{name} must be a ModelLineage value.")


@dataclass(frozen=True, slots=True)
class EmbeddingVector:
    """Validated model output; vectors remain transient outside vector storage."""

    values: tuple[float, ...]
    dimension: int
    normalized: bool
    encoder: ModelLineage

    def __post_init__(self) -> None:
        dimension = _require_int(self.dimension, "dimension", minimum=1)
        if isinstance(self.values, (str, bytes)):
            raise ValueError("values must be a numeric sequence.")
        try:
            values = tuple(float(value) for value in self.values)
        except (TypeError, ValueError) as exc:
            raise ValueError("values must be a numeric sequence.") from exc
        if len(values) != dimension:
            raise ValueError("Embedding length must match dimension.")
        if not all(math.isfinite(value) for value in values):
            raise ValueError("Embedding values must all be finite.")
        if not isinstance(self.normalized, bool):
            raise ValueError("normalized must be a boolean value.")
        if self.normalized:
            norm = math.sqrt(sum(value * value for value in values))
            if not math.isclose(norm, 1.0, rel_tol=1e-5, abs_tol=1e-6):
                raise ValueError("A normalized embedding must have L2 norm 1.")
        if not isinstance(self.encoder, ModelLineage):
            raise ValueError("encoder must be a ModelLineage value.")
        object.__setattr__(self, "values", values)


class PublishedState(StrEnum):
    READY = "READY"


@dataclass(frozen=True, slots=True)
class PublishedTrack:
    """Cross-storage identities returned only after publication reaches READY."""

    track_id: UUID
    object_key: str
    vector_identity: str
    metadata_identity: UUID
    state: PublishedState

    def __post_init__(self) -> None:
        _require_uuid(self.track_id, "track_id")
        _require_nonempty(self.object_key, "object_key")
        _require_nonempty(self.vector_identity, "vector_identity")
        _require_uuid(self.metadata_identity, "metadata_identity")
        if self.metadata_identity != self.track_id:
            raise ValueError("metadata_identity must equal track_id.")
        if self.vector_identity != str(self.track_id):
            raise ValueError("vector_identity must be the canonical track_id string.")
        if self.state is not PublishedState.READY:
            raise ValueError("PublishedTrack may only represent the READY state.")


@dataclass(frozen=True, slots=True)
class BundleArtifact:
    relative_path: str
    sha256: str
    size_bytes: int

    def __post_init__(self) -> None:
        path = Path(_require_nonempty(self.relative_path, "relative_path"))
        if path.is_absolute() or ".." in path.parts:
            raise ValueError("relative_path must remain inside the result bundle.")
        object.__setattr__(self, "sha256", _require_sha256(self.sha256, "sha256"))
        _require_int(self.size_bytes, "size_bytes", minimum=1)


@dataclass(frozen=True, slots=True)
class ResultBundleManifest:
    """Versioned batch result inventory with config, model, track, and artifact lineage."""

    schema_version: str
    source_sha256: str
    ai_config_version_id: UUID
    sampling_interval: int
    detector: ModelLineage
    tracker: ModelLineage
    encoder: ModelLineage
    track_ids: tuple[UUID, ...]
    artifacts: tuple[BundleArtifact, ...]

    def __post_init__(self) -> None:
        _require_nonempty(self.schema_version, "schema_version")
        object.__setattr__(
            self, "source_sha256", _require_sha256(self.source_sha256, "source_sha256")
        )
        _require_uuid(self.ai_config_version_id, "ai_config_version_id")
        _require_int(self.sampling_interval, "sampling_interval", minimum=1)
        for name in ("detector", "tracker", "encoder"):
            if not isinstance(getattr(self, name), ModelLineage):
                raise ValueError(f"{name} must be a ModelLineage value.")
        track_ids = tuple(self.track_ids)
        if not track_ids or not all(isinstance(item, UUID) for item in track_ids):
            raise ValueError("track_ids must contain UUID values.")
        if len(set(track_ids)) != len(track_ids):
            raise ValueError("Bundle track IDs must be unique.")
        object.__setattr__(self, "track_ids", track_ids)
        artifacts = tuple(self.artifacts)
        if not artifacts or not all(isinstance(item, BundleArtifact) for item in artifacts):
            raise ValueError("artifacts must contain BundleArtifact values.")
        if len({item.relative_path for item in artifacts}) != len(artifacts):
            raise ValueError("Bundle artifact paths must be unique.")
        object.__setattr__(self, "artifacts", artifacts)


class ComponentOutcome(StrEnum):
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"
    INCONCLUSIVE = "INCONCLUSIVE"


@dataclass(frozen=True, slots=True)
class ComponentStatus:
    component: str
    outcome: ComponentOutcome
    latency_ms: float
    code: str
    observed_at: datetime

    def __post_init__(self) -> None:
        _require_nonempty(self.component, "component")
        if not isinstance(self.outcome, ComponentOutcome):
            raise ValueError("outcome must be a ComponentOutcome value.")
        latency = _require_finite(self.latency_ms, "latency_ms")
        if latency < 0:
            raise ValueError("latency_ms must not be negative.")
        object.__setattr__(self, "latency_ms", latency)
        _require_nonempty(self.code, "code")
        _require_utc(self.observed_at, "observed_at")


class IdempotentCloseMixin:
    """Reusable close-once behavior for adapters owning external resources."""

    _closed = False

    @property
    def closed(self) -> bool:
        return self._closed

    def close(self) -> None:
        if self._closed:
            return
        try:
            self._close()
        finally:
            self._closed = True

    def _close(self) -> None:
        """Release component-specific resources."""


@runtime_checkable
class FrameSource(Protocol):
    @property
    def metadata(self) -> FrameSourceMetadata: ...

    def open(self, source: str | Path, *, camera_id: UUID) -> Self: ...

    def read(self) -> SourceFrame | None: ...

    def close(self) -> None: ...

    def __iter__(self) -> Iterator[SourceFrame]: ...

    def __enter__(self) -> Self: ...

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None: ...


@runtime_checkable
class Detector(Protocol):
    def open(self) -> None: ...

    def detect(self, frame: SampledFrame) -> Sequence[Detection]: ...

    def close(self) -> None: ...


@runtime_checkable
class Tracker(Protocol):
    def open(self) -> None: ...

    def update(
        self, frame: SampledFrame, detections: Sequence[Detection]
    ) -> Sequence[TrackUpdate]: ...

    def flush(self) -> Sequence[TrackUpdate]: ...

    def close(self) -> None: ...


@runtime_checkable
class ImageEncoder(Protocol):
    def open(self) -> None: ...

    def encode(self, crop: Image.Image) -> EmbeddingVector: ...

    def close(self) -> None: ...


@runtime_checkable
class TextEncoder(Protocol):
    def open(self) -> None: ...

    def encode(self, text: str) -> EmbeddingVector: ...

    def close(self) -> None: ...


@runtime_checkable
class TrackSelector(Protocol):
    def open(self) -> None: ...

    def consider(self, frame: SampledFrame, update: TrackUpdate) -> None: ...

    def flush(self) -> Sequence[CompletedTrack]: ...

    def close(self) -> None: ...


@runtime_checkable
class TrackPublisher(Protocol):
    def open(self) -> None: ...

    def publish(
        self,
        track: CompletedTrack,
        embedding: EmbeddingVector,
        *,
        representative_frame: bytes,
    ) -> PublishedTrack: ...

    def flush(self) -> None: ...

    def close(self) -> None: ...


def public_contract_fields(value: Any) -> Mapping[str, Any]:
    """Return safe scalar identifiers for diagnostics without image/vector payloads."""

    if isinstance(value, SourceFrame):
        return {
            "camera_id": str(value.camera_id),
            "source_frame_index": value.source_frame_index,
            "source_timestamp_ms": value.source_timestamp_ms,
            "width": value.width,
            "height": value.height,
        }
    if isinstance(value, EmbeddingVector):
        return {
            "dimension": value.dimension,
            "normalized": value.normalized,
            "encoder_id": value.encoder.registry_id,
            "encoder_version": value.encoder.version,
        }
    raise TypeError(f"No public diagnostic projection for {type(value).__name__}.")
