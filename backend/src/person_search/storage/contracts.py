"""Executable storage contracts shared by AI workers and storage services."""

from __future__ import annotations

import math
import re
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import StrEnum
from hashlib import sha256
from typing import Final
from uuid import UUID

APPLICATION_FRAME_BUCKET: Final = "person-search-frames"
FRAME_OBJECT_PREFIX: Final = "tracks/v1"
MILVUS_COLLECTION_PREFIX: Final = "person_track_embeddings"
MILVUS_ACTIVE_ALIAS: Final = "person_track_embeddings_active"
RASA_ENCODER_VERSION: Final = "rasa_cuhk_pedes_v1"
RASA_EMBEDDING_DIMENSION: Final = 256
JPEG_MEDIA_TYPE: Final = "image/jpeg"

_ENCODER_VERSION_PATTERN = re.compile(r"^[a-z][a-z0-9_]{2,62}$")
_SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")


class VectorMetric(StrEnum):
    """Vector similarity metrics supported by contract v1."""

    INNER_PRODUCT = "IP"


class TrackStorageState(StrEnum):
    """Durable PersonTrack ingestion states."""

    PENDING = "PENDING"
    READY = "READY"
    FAILED = "FAILED"


_ALLOWED_TRACK_TRANSITIONS: Final = {
    TrackStorageState.PENDING: frozenset(
        {TrackStorageState.PENDING, TrackStorageState.READY, TrackStorageState.FAILED}
    ),
    TrackStorageState.READY: frozenset({TrackStorageState.READY}),
    TrackStorageState.FAILED: frozenset(
        {TrackStorageState.FAILED, TrackStorageState.PENDING}
    ),
}


def can_transition_track_state(
    current: TrackStorageState,
    target: TrackStorageState,
) -> bool:
    """Return whether a durable track state transition is permitted."""

    return target in _ALLOWED_TRACK_TRANSITIONS[current]


def require_uuid4(value: UUID, field_name: str) -> None:
    """Validate the application-wide identifier format."""

    if not isinstance(value, UUID) or value.version != 4:
        raise ValueError(f"{field_name} must be a UUIDv4 value.")


def require_utc(value: datetime, field_name: str) -> None:
    """Require a timezone-aware datetime already normalized to UTC."""

    if (
        not isinstance(value, datetime)
        or value.tzinfo is None
        or value.utcoffset() != timedelta(0)
    ):
        raise ValueError(f"{field_name} must be timezone-aware and normalized to UTC.")


@dataclass(frozen=True, slots=True)
class BoundingBoxPixels:
    """Bounding box in original-frame pixel coordinates."""

    x: int
    y: int
    width: int
    height: int
    frame_width: int
    frame_height: int

    def __post_init__(self) -> None:
        values = (
            self.x,
            self.y,
            self.width,
            self.height,
            self.frame_width,
            self.frame_height,
        )
        if any(isinstance(value, bool) or not isinstance(value, int) for value in values):
            raise ValueError("Bounding box and frame dimensions must be integers.")
        if self.x < 0 or self.y < 0:
            raise ValueError("Bounding box origin must be non-negative.")
        if self.width < 1 or self.height < 1:
            raise ValueError("Bounding box dimensions must be positive.")
        if self.frame_width < 1 or self.frame_height < 1:
            raise ValueError("Frame dimensions must be positive.")
        if self.x + self.width > self.frame_width:
            raise ValueError("Bounding box exceeds the frame width.")
        if self.y + self.height > self.frame_height:
            raise ValueError("Bounding box exceeds the frame height.")


@dataclass(frozen=True, slots=True)
class EncoderManifest:
    """Identity and vector-space constraints for one encoder artifact."""

    version: str
    embedding_dimension: int
    checkpoint_sha256: str
    metric: VectorMetric = VectorMetric.INNER_PRODUCT
    l2_normalized: bool = True

    def __post_init__(self) -> None:
        if not isinstance(self.version, str):
            raise ValueError("Encoder version must be a string.")
        if not isinstance(self.checkpoint_sha256, str):
            raise ValueError("Checkpoint SHA-256 must be a string.")

        normalized_hash = self.checkpoint_sha256.lower()
        object.__setattr__(self, "checkpoint_sha256", normalized_hash)

        if not _ENCODER_VERSION_PATTERN.fullmatch(self.version):
            raise ValueError("Encoder version must use lowercase letters, digits, and underscores.")
        if isinstance(self.embedding_dimension, bool) or not isinstance(
            self.embedding_dimension, int
        ):
            raise ValueError("Embedding dimension must be a positive integer.")
        if self.embedding_dimension < 1:
            raise ValueError("Embedding dimension must be a positive integer.")
        if not _SHA256_PATTERN.fullmatch(normalized_hash):
            raise ValueError("Checkpoint SHA-256 must contain exactly 64 hexadecimal characters.")
        if not isinstance(self.metric, VectorMetric):
            raise ValueError("metric must be a VectorMetric value.")
        if not isinstance(self.l2_normalized, bool):
            raise ValueError("l2_normalized must be a boolean value.")
        if self.version == RASA_ENCODER_VERSION:
            if self.embedding_dimension != RASA_EMBEDDING_DIMENSION:
                raise ValueError("RaSa CUHK-PEDES v1 embeddings must have 256 dimensions.")
            if self.metric is not VectorMetric.INNER_PRODUCT or not self.l2_normalized:
                raise ValueError("RaSa CUHK-PEDES v1 requires L2-normalized vectors and IP.")


@dataclass(frozen=True, slots=True)
class TrackIngestionRequest:
    """Validated payload produced once an AI track is complete."""

    track_id: UUID
    camera_id: UUID
    area_id: UUID
    processing_job_id: UUID
    ai_config_version_id: UUID
    timeline_origin_utc: datetime
    source_frame_index: int
    source_started_at_ms: int
    representative_frame_timestamp_ms: int
    source_ended_at_ms: int
    bbox: BoundingBoxPixels
    frame_bytes: bytes
    embedding: Sequence[float]
    encoder: EncoderManifest
    frame_media_type: str = JPEG_MEDIA_TYPE

    def __post_init__(self) -> None:
        for field_name in (
            "track_id",
            "camera_id",
            "area_id",
            "processing_job_id",
            "ai_config_version_id",
        ):
            require_uuid4(getattr(self, field_name), field_name)

        require_utc(self.timeline_origin_utc, "timeline_origin_utc")
        self._validate_source_timeline()

        if not isinstance(self.bbox, BoundingBoxPixels):
            raise ValueError("bbox must be a BoundingBoxPixels value.")
        if not isinstance(self.encoder, EncoderManifest):
            raise ValueError("encoder must be an EncoderManifest value.")
        if not isinstance(self.frame_bytes, bytes) or not self.frame_bytes:
            raise ValueError("frame_bytes must contain a non-empty JPEG payload.")
        if self.frame_media_type != JPEG_MEDIA_TYPE:
            raise ValueError(f"frame_media_type must be {JPEG_MEDIA_TYPE} in contract v1.")
        is_complete_jpeg = self.frame_bytes.startswith(b"\xff\xd8") and self.frame_bytes.endswith(
            b"\xff\xd9"
        )
        if not is_complete_jpeg:
            raise ValueError("frame_bytes must contain a complete JPEG payload.")

        if isinstance(self.embedding, (str, bytes)):
            raise ValueError("embedding must be a numeric sequence.")
        try:
            normalized_embedding = tuple(float(value) for value in self.embedding)
        except (TypeError, ValueError) as exc:
            raise ValueError("embedding must be a numeric sequence.") from exc
        object.__setattr__(self, "embedding", normalized_embedding)
        self._validate_embedding(normalized_embedding)

    def _validate_source_timeline(self) -> None:
        timeline_values = (
            self.source_frame_index,
            self.source_started_at_ms,
            self.representative_frame_timestamp_ms,
            self.source_ended_at_ms,
        )
        if any(isinstance(value, bool) or not isinstance(value, int) for value in timeline_values):
            raise ValueError("Source frame and timestamp values must be integers.")
        if any(value < 0 for value in timeline_values):
            raise ValueError("Source frame and timestamp values must be non-negative.")
        if self.source_ended_at_ms < self.source_started_at_ms:
            raise ValueError("source_ended_at_ms must not precede source_started_at_ms.")
        if not (
            self.source_started_at_ms
            <= self.representative_frame_timestamp_ms
            <= self.source_ended_at_ms
        ):
            raise ValueError("Representative frame timestamp must be inside the track interval.")

    def _validate_embedding(self, embedding: tuple[float, ...]) -> None:
        if len(embedding) != self.encoder.embedding_dimension:
            raise ValueError("Embedding length does not match the encoder manifest.")
        if not all(math.isfinite(value) for value in embedding):
            raise ValueError("Embedding values must all be finite.")
        if self.encoder.l2_normalized:
            norm = math.sqrt(sum(value * value for value in embedding))
            if not math.isclose(norm, 1.0, rel_tol=1e-5, abs_tol=1e-6):
                raise ValueError("Embedding must be L2-normalized.")

    @property
    def appeared_at_utc(self) -> datetime:
        """Derive the absolute track appearance time from the source timeline."""

        return self.timeline_origin_utc + timedelta(milliseconds=self.source_started_at_ms)

    @property
    def frame_sha256(self) -> str:
        """Compute the identity of the exact immutable frame payload."""

        return sha256(self.frame_bytes).hexdigest()


def frame_object_key(camera_id: UUID, appeared_at_utc: datetime, track_id: UUID) -> str:
    """Build the deterministic MinIO key for a representative full frame."""

    require_uuid4(camera_id, "camera_id")
    require_uuid4(track_id, "track_id")
    require_utc(appeared_at_utc, "appeared_at_utc")
    return (
        f"{FRAME_OBJECT_PREFIX}/{camera_id}/{appeared_at_utc:%Y/%m/%d}/"
        f"{track_id}/representative.jpg"
    )


def milvus_collection_name(encoder_version: str) -> str:
    """Build the physical collection name for one immutable vector space."""

    if not _ENCODER_VERSION_PATTERN.fullmatch(encoder_version):
        raise ValueError("Encoder version must use lowercase letters, digits, and underscores.")
    return f"{MILVUS_COLLECTION_PREFIX}_{encoder_version}"
