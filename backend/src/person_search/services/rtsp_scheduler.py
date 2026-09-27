"""Sequential RTSP session scheduling (architect.md 6.1, UC-04).

When the queue is empty, the worker supervisor asks this scheduler for the next bounded RTSP
session: cameras that are ACTIVE, have AI enabled and an RTSP URL are served round-robin (the
camera whose last RTSP session is oldest goes first). A camera whose latest RTSP session failed
is skipped for a cooldown so one unreachable stream cannot starve the others.
"""

from __future__ import annotations

import logging
import os
import uuid
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select

from person_search.api.errors import ApiError
from person_search.storage.postgres.models import (
    AIConfigStatus,
    AIConfigVersion,
    Camera,
    CameraStatus,
    JobSourceType,
    JobStatus,
    ProcessingJob,
)

LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class CameraCandidate:
    camera_id: uuid.UUID
    code: str
    last_session_at: datetime | None
    last_status: JobStatus | None
    last_ended_at: datetime | None


def choose_camera(
    candidates: Iterable[CameraCandidate], *, now: datetime, failure_cooldown: timedelta
) -> uuid.UUID | None:
    """Pick the least recently served camera, skipping ones in failure cooldown."""

    eligible = [
        item
        for item in candidates
        if not (
            item.last_status == JobStatus.FAILED
            and item.last_ended_at is not None
            and now - item.last_ended_at < failure_cooldown
        )
    ]
    if not eligible:
        return None
    oldest = min(
        eligible,
        key=lambda item: (
            item.last_session_at is not None,
            item.last_session_at or datetime.min.replace(tzinfo=UTC),
            item.code,
        ),
    )
    return oldest.camera_id


@dataclass(frozen=True, slots=True)
class RtspSchedulerSettings:
    enabled: bool = True
    session_frames: int = 1800
    sampling_profile: str = "throughput"
    failure_cooldown: timedelta = timedelta(minutes=5)

    @classmethod
    def from_environment(cls) -> RtspSchedulerSettings:
        frames = int(os.getenv("PERSON_SEARCH_RTSP_SESSION_FRAMES", "1800"))
        cooldown = int(os.getenv("PERSON_SEARCH_RTSP_FAILURE_COOLDOWN_SECONDS", "300"))
        if frames < 1 or cooldown < 0:
            raise ValueError("RTSP session frames must be positive and cooldown non-negative.")
        return cls(
            enabled=os.getenv("PERSON_SEARCH_RTSP_AUTO", "1").strip() != "0",
            session_frames=frames,
            sampling_profile=os.getenv("PERSON_SEARCH_RTSP_SAMPLING_PROFILE", "throughput"),
            failure_cooldown=timedelta(seconds=cooldown),
        )


class RtspSessionScheduler:
    def __init__(
        self,
        unit_of_work_factory: Callable,
        jobs,
        settings: RtspSchedulerSettings,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self.unit_of_work_factory = unit_of_work_factory
        self.jobs = jobs
        self.settings = settings
        self.clock = clock

    def _candidates(self, work) -> list[CameraCandidate]:
        session = work.session
        busy = session.scalar(
            select(func.count())
            .select_from(ProcessingJob)
            .where(ProcessingJob.status.in_((JobStatus.PENDING, JobStatus.RUNNING)))
        )
        active_config = session.scalar(
            select(AIConfigVersion.id).where(AIConfigVersion.status == AIConfigStatus.ACTIVE)
        )
        if busy or active_config is None:
            return []
        cameras = session.execute(
            select(Camera.id, Camera.code).where(
                Camera.status == CameraStatus.ACTIVE,
                Camera.ai_enabled.is_(True),
                Camera.rtsp_url.is_not(None),
            )
        ).all()
        candidates = []
        for camera_id, code in cameras:
            last = session.execute(
                select(ProcessingJob.created_at, ProcessingJob.status, ProcessingJob.ended_at)
                .where(
                    ProcessingJob.camera_id == camera_id,
                    ProcessingJob.source_type == JobSourceType.RTSP,
                )
                .order_by(ProcessingJob.created_at.desc())
                .limit(1)
            ).first()
            candidates.append(
                CameraCandidate(camera_id, code, *(last if last else (None, None, None)))
            )
        return candidates

    def enqueue_next(self) -> dict | None:
        """Create one bounded RTSP job when the queue is idle; return it, or None."""

        if not self.settings.enabled:
            return None
        with self.unit_of_work_factory() as work:
            camera_id = choose_camera(
                self._candidates(work),
                now=self.clock(),
                failure_cooldown=self.settings.failure_cooldown,
            )
        if camera_id is None:
            return None
        try:
            job = self.jobs.create_rtsp_job(
                camera_id,
                None,
                max_source_frames=self.settings.session_frames,
                sampling_profile=self.settings.sampling_profile,
            )
        except ApiError as error:
            # The camera changed between selection and creation (AI off, retired, config gone).
            LOGGER.info(
                "rtsp session skipped", extra={"camera_id": str(camera_id), "code": error.code}
            )
            return None
        LOGGER.info("rtsp session queued", extra={"camera_id": str(camera_id), "job_id": job["id"]})
        return job
