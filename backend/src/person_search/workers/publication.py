"""Production publication bridge from AI tracks to the three-store invariant."""

from __future__ import annotations

import hashlib
import io
import json
import logging
import uuid
from base64 import b64decode, b64encode
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Protocol

from person_search.observability import log_context
from person_search.services.track_ingestion import TrackIngestionConflictError
from person_search.storage.contracts import (
    BoundingBoxPixels,
    EncoderManifest,
    TrackIngestionRequest,
)
from person_search.storage.postgres.models import TrackIndexStatus
from person_search.workers.durable import JobExecutionSnapshot
from person_search.workers.errors import AIErrorCode, AIWorkerError
from person_search.workers.production import EncodedTrack, ProductionPipelineResult

logger = logging.getLogger(__name__)


class TrackPublisher(Protocol):
    def ingest_track(
        self, request: TrackIngestionRequest, *, correlation_id: str | None = None
    ): ...


def stable_track_id(job_id: uuid.UUID, local_track_id: str) -> uuid.UUID:
    """Return a retry-stable UUIDv4 without leaking tracker-local identifiers."""

    digest = bytearray(hashlib.sha256(f"{job_id}:{local_track_id}".encode()).digest()[:16])
    digest[6] = (digest[6] & 0x0F) | 0x40
    digest[8] = (digest[8] & 0x3F) | 0x80
    return uuid.UUID(bytes=bytes(digest))


def ingestion_request(
    snapshot: JobExecutionSnapshot, area_id: uuid.UUID, encoded: EncodedTrack
) -> TrackIngestionRequest:
    """Serialize exactly one complete representative frame; never persist its crop."""

    track = encoded.track
    if (
        track.processing_job_id != snapshot.job_id
        or track.camera_id != snapshot.camera_id
        or track.ai_config_version_id != snapshot.ai_config_version_id
        or track.sampling_interval != snapshot.sampling_interval
    ):
        raise ValueError("Encoded track lineage does not match the claimed job snapshot.")
    frame = track.representative.frame
    payload = io.BytesIO()
    frame.image.save(payload, format="JPEG", quality=90)
    return TrackIngestionRequest(
        track_id=stable_track_id(snapshot.job_id, track.local_track_id),
        camera_id=track.camera_id,
        area_id=area_id,
        processing_job_id=track.processing_job_id,
        ai_config_version_id=track.ai_config_version_id,
        timeline_origin_utc=snapshot.timeline_origin_utc,
        source_frame_index=frame.source_frame_index,
        source_started_at_ms=track.source_started_at_ms,
        representative_frame_timestamp_ms=frame.source_timestamp_ms,
        source_ended_at_ms=track.source_ended_at_ms,
        bbox=track.representative.bbox,
        frame_bytes=payload.getvalue(),
        embedding=encoded.embedding.values,
        encoder=EncoderManifest(
            version=track.encoder.version,
            embedding_dimension=encoded.embedding.dimension,
            checkpoint_sha256=track.encoder.artifact_sha256,
            l2_normalized=encoded.embedding.normalized,
        ),
    )


@dataclass(slots=True)
class ProductionTrackPublisher:
    """Publish pipeline output only through ``TrackIngestionService``."""

    ingestion: TrackPublisher
    area_id: uuid.UUID
    jobs: object

    def __call__(self, snapshot: JobExecutionSnapshot, result: ProductionPipelineResult) -> None:
        published = snapshot.published_tracks
        for ordinal, encoded in enumerate(result.encoded_tracks, start=1):
            request = ingestion_request(snapshot, self.area_id, encoded)
            with log_context(track_id=request.track_id):
                try:
                    outcome = self.ingestion.ingest_track(
                        request, correlation_id=f"job-{snapshot.job_id.hex}"
                    )
                except TrackIngestionConflictError as error:
                    logger.warning(
                        "track publication conflict", extra={"error_type": type(error).__name__}
                    )
                    raise AIWorkerError(AIErrorCode.STORAGE_CONFLICT, cause=error) from error
                except Exception as error:
                    logger.warning(
                        "track publication failed", extra={"error_type": type(error).__name__}
                    )
                    raise AIWorkerError(AIErrorCode.STORAGE_UNAVAILABLE, cause=error) from error
            if outcome.status is not TrackIndexStatus.READY:
                raise AIWorkerError(
                    AIErrorCode.STORAGE_PUBLISH_FAILED,
                    internal_detail=f"track {request.track_id} remains {outcome.status.value}",
                )
            published = max(snapshot.published_tracks, ordinal)
            if not self.jobs.checkpoint(
                snapshot.job_id,
                snapshot.lease_token,
                result.source_frames,
                result.sampled_frames,
                len(result.encoded_tracks),
                published,
            ):
                raise AIWorkerError(AIErrorCode.CANCELLED)


BUNDLE_SCHEMA = "person-search-result-bundle/v1"


class BundleValidationError(ValueError):
    pass


class BundlePublisher:
    """Export a checksum-protected local/Colab handoff without touching storage."""

    def write(
        self,
        path: Path,
        snapshot: JobExecutionSnapshot,
        area_id: uuid.UUID,
        result: ProductionPipelineResult,
    ) -> None:
        tracks = []
        for encoded in result.encoded_tracks:
            request = ingestion_request(snapshot, area_id, encoded)
            track = encoded.track
            record = {
                "track_id": str(request.track_id),
                "local_track_id": track.local_track_id,
                "camera_id": str(request.camera_id),
                "area_id": str(request.area_id),
                "processing_job_id": str(request.processing_job_id),
                "ai_config_version_id": str(request.ai_config_version_id),
                "timeline_origin_utc": request.timeline_origin_utc.isoformat(),
                "source_frame_index": request.source_frame_index,
                "source_started_at_ms": request.source_started_at_ms,
                "representative_frame_timestamp_ms": request.representative_frame_timestamp_ms,
                "source_ended_at_ms": request.source_ended_at_ms,
                "bbox": {
                    key: getattr(request.bbox, key)
                    for key in ("x", "y", "width", "height", "frame_width", "frame_height")
                },
                "frame_jpeg_base64": b64encode(request.frame_bytes).decode("ascii"),
                "frame_sha256": request.frame_sha256,
                "embedding": list(request.embedding),
                "encoder": {
                    "registry_id": track.encoder.registry_id,
                    "version": request.encoder.version,
                    "dimension": request.encoder.embedding_dimension,
                    "checkpoint_sha256": request.encoder.checkpoint_sha256,
                },
                "detector": _lineage(track.detector),
                "tracker": _lineage(track.tracker),
                "sampling_interval": track.sampling_interval,
            }
            tracks.append(record)
        document = {"schema": BUNDLE_SCHEMA, "tracks": tracks}
        path.write_text(
            json.dumps(document, sort_keys=True, separators=(",", ":")), encoding="utf-8"
        )


@dataclass(slots=True)
class BundleImporter:
    """Verify a bundle and publish each item through the same ingestion invariant."""

    ingestion: TrackPublisher
    expected_config_id: uuid.UUID
    expected_encoder: EncoderManifest

    def import_file(self, path: Path) -> int:
        try:
            document = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as error:
            raise BundleValidationError("Bundle is not valid UTF-8 JSON.") from error
        if set(document) != {"schema", "tracks"} or document["schema"] != BUNDLE_SCHEMA:
            raise BundleValidationError("Bundle schema is unsupported.")
        if not isinstance(document["tracks"], list):
            raise BundleValidationError("Bundle tracks must be a list.")
        ready = 0
        seen: set[uuid.UUID] = set()
        for item in document["tracks"]:
            request = self._request(item)
            if request.track_id in seen:
                raise BundleValidationError("Bundle contains a duplicate track ID.")
            seen.add(request.track_id)
            outcome = self.ingestion.ingest_track(
                request, correlation_id=f"bundle-{request.processing_job_id.hex}"
            )
            if outcome.status is not TrackIndexStatus.READY:
                raise AIWorkerError(AIErrorCode.STORAGE_PUBLISH_FAILED)
            ready += 1
        return ready

    def _request(self, item: object) -> TrackIngestionRequest:
        if not isinstance(item, dict):
            raise BundleValidationError("Bundle track must be an object.")
        try:
            frame = b64decode(item["frame_jpeg_base64"], validate=True)
            encoder = item["encoder"]
            track_id = uuid.UUID(item["track_id"])
            job_id = uuid.UUID(item["processing_job_id"])
            if track_id != stable_track_id(job_id, item["local_track_id"]):
                raise BundleValidationError("Bundle track identity does not match its lineage.")
            if uuid.UUID(item["ai_config_version_id"]) != self.expected_config_id:
                raise BundleValidationError("Bundle configuration lineage does not match.")
            if (
                encoder["version"] != self.expected_encoder.version
                or encoder["dimension"] != self.expected_encoder.embedding_dimension
                or encoder["checkpoint_sha256"] != self.expected_encoder.checkpoint_sha256
            ):
                raise BundleValidationError("Bundle encoder lineage does not match.")
            _validate_component_lineage(item["detector"])
            _validate_component_lineage(item["tracker"])
            if hashlib.sha256(frame).hexdigest() != item["frame_sha256"]:
                raise BundleValidationError("Bundle frame checksum does not match.")
            return TrackIngestionRequest(
                track_id=track_id,
                camera_id=uuid.UUID(item["camera_id"]),
                area_id=uuid.UUID(item["area_id"]),
                processing_job_id=job_id,
                ai_config_version_id=uuid.UUID(item["ai_config_version_id"]),
                timeline_origin_utc=datetime.fromisoformat(item["timeline_origin_utc"]),
                source_frame_index=item["source_frame_index"],
                source_started_at_ms=item["source_started_at_ms"],
                representative_frame_timestamp_ms=item["representative_frame_timestamp_ms"],
                source_ended_at_ms=item["source_ended_at_ms"],
                bbox=BoundingBoxPixels(**item["bbox"]),
                frame_bytes=frame,
                embedding=item["embedding"],
                encoder=self.expected_encoder,
            )
        except BundleValidationError:
            raise
        except (KeyError, TypeError, ValueError) as error:
            raise BundleValidationError("Bundle track payload is invalid.") from error


def _lineage(value) -> dict[str, str]:
    return {
        "registry_id": value.registry_id,
        "version": value.version,
        "artifact_sha256": value.artifact_sha256,
    }


def _validate_component_lineage(value: object) -> None:
    if not isinstance(value, dict) or set(value) != {
        "registry_id",
        "version",
        "artifact_sha256",
    }:
        raise BundleValidationError("Bundle model lineage is invalid.")
    if not value["registry_id"] or not value["version"]:
        raise BundleValidationError("Bundle model lineage is invalid.")
    checksum = value["artifact_sha256"]
    try:
        valid_checksum = len(checksum) == 64 and int(checksum, 16) >= 0
    except (TypeError, ValueError):
        valid_checksum = False
    if not valid_checksum:
        raise BundleValidationError("Bundle model lineage is invalid.")
