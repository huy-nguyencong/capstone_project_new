from __future__ import annotations

import logging
import uuid
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Any, Protocol

from person_search.storage.contracts import TrackIngestionRequest, frame_object_key
from person_search.storage.milvus.vectors import CollectionContractError, InvalidVectorError
from person_search.storage.minio.frames import FrameConflictError, FrameInfo, InvalidFrameError
from person_search.storage.postgres.errors import DuplicateEntityError
from person_search.storage.postgres.models import (
    OutboxStatus,
    PersonTrack,
    StorageOutboxEvent,
    TrackIndexStatus,
)
from person_search.storage.postgres.repositories import Repositories
from person_search.storage.postgres.unit_of_work import UnitOfWork

logger = logging.getLogger(__name__)

TRACK_INGEST_EVENT = "track.ingest"
OUTBOX_PAYLOAD_VERSION = 1


class TrackIngestionError(RuntimeError):
    pass


class TrackIngestionConflictError(TrackIngestionError):
    pass


class TrackReferenceError(TrackIngestionError):
    pass


class TrackNotPublishableError(TrackIngestionError):
    pass


class IngestionStep(StrEnum):
    FRAME_UPLOAD = "FRAME_UPLOAD"
    VECTOR_UPSERT = "VECTOR_UPSERT"
    PUBLISH = "PUBLISH"


NON_RETRYABLE_ERRORS: tuple[type[BaseException], ...] = (
    TrackIngestionError,
    FrameConflictError,
    InvalidFrameError,
    InvalidVectorError,
    CollectionContractError,
    ValueError,
)


def is_retryable(error: BaseException) -> bool:
    return not isinstance(error, NON_RETRYABLE_ERRORS)


class FrameStore(Protocol):
    def put_frame(
        self,
        *,
        camera_id: uuid.UUID,
        track_id: uuid.UUID,
        captured_at: datetime,
        data: bytes,
        content_type: str,
        width: int,
        height: int,
    ) -> FrameInfo: ...


class VectorIndex(Protocol):
    encoder_version: str

    def upsert(
        self,
        *,
        track_id: uuid.UUID,
        vector: Sequence[float],
        area_id: uuid.UUID,
        camera_id: uuid.UUID,
        appeared_at: datetime,
    ) -> None: ...


@dataclass(frozen=True, slots=True)
class RetryPolicy:
    max_attempts: int = 5
    base_delay_seconds: float = 2.0
    max_delay_seconds: float = 300.0

    def __post_init__(self) -> None:
        if self.max_attempts < 1:
            raise ValueError("max_attempts must be positive")
        if self.base_delay_seconds <= 0 or self.max_delay_seconds < self.base_delay_seconds:
            raise ValueError("retry delays must be positive and ordered")

    def delay_after(self, attempts: int) -> timedelta:
        seconds = self.base_delay_seconds * 2 ** max(attempts - 1, 0)
        return timedelta(seconds=min(seconds, self.max_delay_seconds))


@dataclass(frozen=True, slots=True)
class TrackIngestionResult:
    track_id: uuid.UUID
    status: TrackIndexStatus
    correlation_id: str
    failure_code: str | None = None
    retryable: bool = False


def _utc_now() -> datetime:
    return datetime.now(UTC)


class TrackIngestionService:
    def __init__(
        self,
        unit_of_work_factory: Callable[[], UnitOfWork],
        frames: FrameStore,
        vectors: VectorIndex,
        *,
        retry_policy: RetryPolicy | None = None,
        clock: Callable[[], datetime] = _utc_now,
    ) -> None:
        self._unit_of_work_factory = unit_of_work_factory
        self._frames = frames
        self._vectors = vectors
        self._retry_policy = retry_policy or RetryPolicy()
        self._clock = clock

    def ingest_track(
        self, request: TrackIngestionRequest, *, correlation_id: str | None = None
    ) -> TrackIngestionResult:
        correlation_id = correlation_id or uuid.uuid4().hex
        status = self._register(request, correlation_id)
        if status is not TrackIndexStatus.PENDING:
            logger.info(
                "track ingestion skipped",
                extra={
                    "correlation_id": correlation_id,
                    "track_id": str(request.track_id),
                    "status": status.value,
                },
            )
            return TrackIngestionResult(request.track_id, status, correlation_id)

        step = IngestionStep.FRAME_UPLOAD
        try:
            self._upload_frame(request)
            step = IngestionStep.VECTOR_UPSERT
            self._vectors.upsert(
                track_id=request.track_id,
                vector=request.embedding,
                area_id=request.area_id,
                camera_id=request.camera_id,
                appeared_at=request.appeared_at_utc,
            )
            step = IngestionStep.PUBLISH
            self._publish(request.track_id)
        except Exception as error:
            return self._record_failure(request.track_id, correlation_id, step, error)

        logger.info(
            "track ingestion published",
            extra={"correlation_id": correlation_id, "track_id": str(request.track_id)},
        )
        return TrackIngestionResult(request.track_id, TrackIndexStatus.READY, correlation_id)

    def _register(self, request: TrackIngestionRequest, correlation_id: str) -> TrackIndexStatus:
        try:
            with self._unit_of_work_factory() as work:
                repositories = self._repositories(work)
                track = repositories.tracks.get_for_update(request.track_id)
                if track is not None:
                    _require_same_identity(track, request)
                    return track.index_status
                self._validate_references(repositories, request)
                repositories.tracks.add(_new_track(request))
                work.flush()
                repositories.outbox.add(
                    StorageOutboxEvent(
                        id=uuid.uuid4(),
                        track_id=request.track_id,
                        event_type=TRACK_INGEST_EVENT,
                        payload=_outbox_payload(request, correlation_id),
                        status=OutboxStatus.PENDING,
                        attempts=0,
                        available_at=self._clock(),
                    )
                )
                work.commit()
                return TrackIndexStatus.PENDING
        except DuplicateEntityError:
            with self._unit_of_work_factory() as work:
                track = self._repositories(work).tracks.get_for_update(request.track_id)
                if track is None:
                    raise
                _require_same_identity(track, request)
                return track.index_status

    def _validate_references(
        self, repositories: Repositories, request: TrackIngestionRequest
    ) -> None:
        camera = repositories.cameras.get(request.camera_id)
        if camera is None:
            raise TrackReferenceError("Camera does not exist.")
        if camera.area_id != request.area_id:
            raise TrackReferenceError("Camera area does not match the request area.")
        job = repositories.jobs.get(request.processing_job_id)
        if job is None or job.camera_id != request.camera_id:
            raise TrackReferenceError("Processing job does not belong to the camera.")
        if job.ai_config_version_id != request.ai_config_version_id:
            raise TrackReferenceError("Processing job uses a different AI config version.")
        config = repositories.ai_configs.get(request.ai_config_version_id)
        if config is None:
            raise TrackReferenceError("AI config version does not exist.")
        encoder = request.encoder
        if (
            config.encoder_version != encoder.version
            or config.encoder_dimension != encoder.embedding_dimension
            or config.checkpoint_sha256.lower() != encoder.checkpoint_sha256
        ):
            raise TrackReferenceError("Encoder manifest does not match the AI config version.")
        if self._vectors.encoder_version != encoder.version:
            raise TrackReferenceError("Vector index serves a different encoder version.")

    def _upload_frame(self, request: TrackIngestionRequest) -> None:
        info = self._frames.put_frame(
            camera_id=request.camera_id,
            track_id=request.track_id,
            captured_at=request.appeared_at_utc,
            data=request.frame_bytes,
            content_type=request.frame_media_type,
            width=request.bbox.frame_width,
            height=request.bbox.frame_height,
        )
        expected_key = frame_object_key(
            request.camera_id, request.appeared_at_utc, request.track_id
        )
        if info.object_key != expected_key:
            raise FrameConflictError("Stored frame key does not match the contract key.")
        if info.checksum_sha256 != request.frame_sha256:
            raise FrameConflictError("Stored frame checksum does not match the request.")

    def _publish(self, track_id: uuid.UUID) -> None:
        with self._unit_of_work_factory() as work:
            repositories = self._repositories(work)
            track = repositories.tracks.get_for_update(track_id)
            if track is None:
                raise TrackNotPublishableError("Track disappeared before publishing.")
            if track.index_status is TrackIndexStatus.READY:
                return
            if track.index_status is not TrackIndexStatus.PENDING:
                raise TrackNotPublishableError("Only a PENDING track can be published.")
            now = self._clock()
            track.vector_indexed_at = now
            track.index_status = TrackIndexStatus.READY
            track.failure_code = None
            track.failure_message = None
            event = repositories.outbox.get_for_track(
                track_id, TRACK_INGEST_EVENT, for_update=True
            )
            if event is not None:
                event.status = OutboxStatus.COMPLETED
                event.processed_at = now
                event.locked_at = None
                event.last_error = None
            work.commit()

    def _record_failure(
        self,
        track_id: uuid.UUID,
        correlation_id: str,
        step: IngestionStep,
        error: Exception,
    ) -> TrackIngestionResult:
        retryable = is_retryable(error)
        failure_code = f"{step.value}_FAILED"
        failure_message = f"{step.value} raised {type(error).__name__}."
        logger.warning(
            "track ingestion step failed",
            extra={
                "correlation_id": correlation_id,
                "track_id": str(track_id),
                "step": step.value,
                "error_type": type(error).__name__,
                "retryable": retryable,
            },
        )
        with self._unit_of_work_factory() as work:
            repositories = self._repositories(work)
            track = repositories.tracks.get_for_update(track_id)
            if track is None or track.index_status is not TrackIndexStatus.PENDING:
                status = track.index_status if track is not None else TrackIndexStatus.FAILED
                return TrackIngestionResult(track_id, status, correlation_id, failure_code)
            event = repositories.outbox.get_for_track(
                track_id, TRACK_INGEST_EVENT, for_update=True
            )
            now = self._clock()
            attempts = (event.attempts if event is not None else 0) + 1
            exhausted = attempts >= self._retry_policy.max_attempts
            will_retry = retryable and not exhausted
            track.failure_code = failure_code
            track.failure_message = failure_message
            if not will_retry:
                track.index_status = TrackIndexStatus.FAILED
            if event is not None:
                event.attempts = attempts
                event.last_error = failure_message
                event.locked_at = None
                if will_retry:
                    event.status = OutboxStatus.PENDING
                    event.available_at = now + self._retry_policy.delay_after(attempts)
                else:
                    event.status = OutboxStatus.DEAD
            work.commit()
        status = TrackIndexStatus.PENDING if will_retry else TrackIndexStatus.FAILED
        return TrackIngestionResult(track_id, status, correlation_id, failure_code, will_retry)

    @staticmethod
    def _repositories(work: UnitOfWork) -> Repositories:
        assert work.repositories is not None
        return work.repositories


def _new_track(request: TrackIngestionRequest) -> PersonTrack:
    bbox = request.bbox
    return PersonTrack(
        id=request.track_id,
        camera_id=request.camera_id,
        processing_job_id=request.processing_job_id,
        ai_config_version_id=request.ai_config_version_id,
        appeared_at_utc=request.appeared_at_utc,
        source_started_at_ms=request.source_started_at_ms,
        source_ended_at_ms=request.source_ended_at_ms,
        representative_frame_timestamp_ms=request.representative_frame_timestamp_ms,
        bbox_x=bbox.x,
        bbox_y=bbox.y,
        bbox_width=bbox.width,
        bbox_height=bbox.height,
        frame_width=bbox.frame_width,
        frame_height=bbox.frame_height,
        minio_object_key=frame_object_key(
            request.camera_id, request.appeared_at_utc, request.track_id
        ),
        frame_sha256=request.frame_sha256,
        frame_size_bytes=len(request.frame_bytes),
        encoder_version=request.encoder.version,
        index_status=TrackIndexStatus.PENDING,
    )


def _track_identity(track: PersonTrack) -> tuple[Any, ...]:
    return (
        track.camera_id,
        track.processing_job_id,
        track.ai_config_version_id,
        track.appeared_at_utc,
        track.source_started_at_ms,
        track.source_ended_at_ms,
        track.representative_frame_timestamp_ms,
        track.bbox_x,
        track.bbox_y,
        track.bbox_width,
        track.bbox_height,
        track.frame_width,
        track.frame_height,
        track.frame_sha256,
        track.encoder_version,
    )


def _require_same_identity(track: PersonTrack, request: TrackIngestionRequest) -> None:
    if _track_identity(track) != _track_identity(_new_track(request)):
        raise TrackIngestionConflictError(
            "A track with the same ID already exists with a different payload identity."
        )


def _outbox_payload(request: TrackIngestionRequest, correlation_id: str) -> dict[str, Any]:
    return {
        "version": OUTBOX_PAYLOAD_VERSION,
        "correlation_id": correlation_id,
        "area_id": str(request.area_id),
        "camera_id": str(request.camera_id),
        "appeared_at_utc": request.appeared_at_utc.isoformat(),
        "frame_object_key": frame_object_key(
            request.camera_id, request.appeared_at_utc, request.track_id
        ),
        "frame_sha256": request.frame_sha256,
        "encoder_version": request.encoder.version,
        "embedding": list(request.embedding),
    }
