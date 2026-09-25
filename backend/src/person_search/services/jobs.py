"""Admin upload API and durable, sequential processing queue."""

import base64
import hashlib
import json
import re
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, or_, select, text

from person_search.api.errors import ApiError
from person_search.services.audit import AuditEvent, record_audit
from person_search.services.cameras import identifier, iso
from person_search.storage.postgres.models import (
    AIConfigStatus,
    AIConfigVersion,
    AuditResult,
    Camera,
    CameraStatus,
    JobSourceType,
    JobStatus,
    PersonTrack,
    ProcessingJob,
    TrackIndexStatus,
)

TERMINAL = {JobStatus.SUCCEEDED, JobStatus.FAILED, JobStatus.CANCELLED}


class JobService:
    def __init__(self, factory, staging, clock=lambda: datetime.now(UTC)):
        self.factory, self.staging, self.clock = factory, staging, clock

    def row(self, work, job_id, lock=False):
        query = select(ProcessingJob).where(ProcessingJob.id == identifier(job_id))
        row = work.session.scalar(query.with_for_update() if lock else query)
        if row is None:
            raise ApiError(404, "job_not_found", "Không tìm thấy tác vụ.")
        return row

    def view(self, work, job):
        camera = work.session.get(Camera, job.camera_id)
        counts = dict(
            work.session.execute(
                select(PersonTrack.index_status, func.count())
                .where(PersonTrack.processing_job_id == job.id)
                .group_by(PersonTrack.index_status)
            ).all()
        )
        config = work.session.get(AIConfigVersion, job.ai_config_version_id)
        return dict(
            id=str(job.id),
            camera={"id": str(camera.id), "name": camera.name},
            source_type=job.source_type.value,
            status=job.status.value,
            processed_frames=job.processed_frames,
            total_frames=job.total_frames,
            sampled_frames=job.sampled_frames,
            sampling_interval=job.sampling_interval,
            tracks_ready=counts.get(TrackIndexStatus.READY, 0),
            tracks_failed=counts.get(TrackIndexStatus.FAILED, 0),
            tracks_pending=counts.get(TrackIndexStatus.PENDING, 0),
            recorded_started_at=iso(job.timeline_origin_utc),
            created_at=iso(job.created_at),
            started_at=iso(job.started_at),
            ended_at=iso(job.ended_at),
            error_code=job.error_code,
            error_message=job.error_message,
            cancel_requested=job.cancel_requested,
            pipeline_mode="DEMO" if config.encoder_version == "fake_demo_v1" else "AI",
        )

    def audit(self, work, event, job, actor=None):
        record_audit(
            work.repositories,
            event_type=event,
            result=AuditResult.FAILURE if job.status == JobStatus.FAILED else AuditResult.SUCCESS,
            target_type="processing_job",
            target_id=job.id,
            actor_user_id=actor,
            metadata={"status": job.status.value},
        )

    def eligible(self, work, camera_id, lock=False):
        query = select(Camera).where(Camera.id == identifier(camera_id))
        camera = work.session.scalar(query.with_for_update() if lock else query)
        if camera is None:
            raise ApiError(404, "camera_not_found", "Không tìm thấy camera.")
        if camera.status != CameraStatus.ACTIVE:
            raise ApiError(409, "camera_not_active", "Camera đã ngừng vận hành.")
        if not camera.ai_enabled:
            raise ApiError(409, "camera_ai_disabled", "Hãy bật xử lý AI cho camera trước.")
        config = work.session.scalar(
            select(AIConfigVersion).where(AIConfigVersion.status == AIConfigStatus.ACTIVE)
        )
        if config is None:
            raise ApiError(409, "ai_config_missing", "Chưa có cấu hình AI.")
        return camera, config

    def upload(self, camera_id, actor_id, key, form, upload):
        if not key or not re.fullmatch(r"[A-Za-z0-9._:-]{8,128}", key):
            raise ApiError(422, "invalid_idempotency_key", "Cần Idempotency-Key dài 8–128 ký tự.")
        if set(form) - {"recorded_started_at", "sampling_interval"}:
            raise ApiError(422, "invalid_fields", "Có trường upload không hợp lệ.")
        try:
            origin = datetime.fromisoformat(
                form.get("recorded_started_at", "").replace("Z", "+00:00")
            )
            if origin.tzinfo is None:
                raise ValueError
            origin = origin.astimezone(UTC)
            sampling = int(form.get("sampling_interval", "10"))
            if not 1 <= sampling <= 1000:
                raise ValueError
        except (ValueError, TypeError):
            raise ApiError(
                422, "invalid_video_metadata", "Cần thời điểm có múi giờ và sampling 1–1000."
            ) from None
        if upload is None:
            raise ApiError(422, "file_required", "Vui lòng chọn video.")
        # Fail early for a new upload, but allow an exact retry after camera retirement.
        with self.factory() as work:
            old = work.session.scalar(
                select(ProcessingJob).where(
                    ProcessingJob.requested_by == actor_id, ProcessingJob.idempotency_key == key
                )
            )
            if old is None:
                self.eligible(work, camera_id)
        staged = self.staging.stage(upload)
        keep = False
        try:
            digest = hashlib.sha256(
                json.dumps(
                    [str(identifier(camera_id)), iso(origin), sampling, staged.digest]
                ).encode()
            ).hexdigest()
            with self.factory() as work:
                lock_id = int.from_bytes(
                    hashlib.sha256(f"{actor_id}:{key}".encode()).digest()[:8], "big", signed=True
                )
                work.session.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": lock_id})
                old = work.session.scalar(
                    select(ProcessingJob).where(
                        ProcessingJob.requested_by == actor_id, ProcessingJob.idempotency_key == key
                    )
                )
                if old:
                    if old.request_digest != digest:
                        raise ApiError(
                            409, "idempotency_conflict", "Khóa này đã dùng cho nội dung khác."
                        )
                    return self.view(work, old)
                camera, config = self.eligible(work, camera_id, lock=True)
                job = ProcessingJob(
                    id=uuid.uuid4(),
                    camera_id=camera.id,
                    ai_config_version_id=config.id,
                    requested_by=actor_id,
                    idempotency_key=key,
                    request_digest=digest,
                    source_type=JobSourceType.FILE,
                    source_ref=staged.name,
                    status=JobStatus.PENDING,
                    sampling_interval=sampling,
                    timeline_origin_utc=origin,
                    processed_frames=0,
                    sampled_frames=0,
                    total_frames=staged.total_frames,
                    attempts=0,
                    cancel_requested=False,
                )
                work.session.add(job)
                self.audit(work, AuditEvent.JOB_CREATED, job, actor_id)
                work.commit()
                keep = True
                return self.view(work, job)
        finally:
            if not keep:
                self.staging.remove(staged.name)

    def get(self, job_id):
        with self.factory() as work:
            return self.view(work, self.row(work, job_id))

    def list(self, args):
        try:
            limit = int(args.get("limit", 20))
            if not 1 <= limit <= 100:
                raise ValueError
            query = select(ProcessingJob).order_by(
                ProcessingJob.created_at.desc(), ProcessingJob.id.desc()
            )
            if args.get("status"):
                query = query.where(ProcessingJob.status == JobStatus(args["status"]))
            if args.get("camera_id"):
                query = query.where(ProcessingJob.camera_id == identifier(args["camera_id"]))
            if args.get("cursor"):
                at, last_id = json.loads(
                    base64.b64decode(args["cursor"], altchars=b"-_", validate=True)
                )
                timestamp = datetime.fromisoformat(at)
                if timestamp.tzinfo is None:
                    raise ValueError
                query = query.where(
                    or_(
                        ProcessingJob.created_at < timestamp,
                        (ProcessingJob.created_at == timestamp)
                        & (ProcessingJob.id < identifier(last_id)),
                    )
                )
        except (ValueError, TypeError):
            raise ApiError(422, "invalid_filter", "Bộ lọc hoặc cursor không hợp lệ.") from None
        with self.factory() as work:
            rows = list(work.session.scalars(query.limit(limit + 1)))
            cursor = None
            if len(rows) > limit:
                last = rows[limit - 1]
                cursor = base64.urlsafe_b64encode(
                    json.dumps([iso(last.created_at), str(last.id)]).encode()
                ).decode()
            return {"items": [self.view(work, row) for row in rows[:limit]], "next_cursor": cursor}

    def cancel(self, job_id, actor_id):
        remove = None
        with self.factory() as work:
            job = self.row(work, job_id, lock=True)
            if job.status not in TERMINAL and not job.cancel_requested:
                job.cancel_requested = True
                if job.status == JobStatus.PENDING:
                    job.status, job.ended_at = JobStatus.CANCELLED, self.clock()
                    remove = job.source_ref
                self.audit(work, AuditEvent.JOB_CANCEL_REQUESTED, job, actor_id)
                work.commit()
            result = self.view(work, job)
        if remove:
            self.staging.remove(remove)
        return result

    def claim(self):
        """Caller must own the global worker advisory lock for the whole run."""
        with self.factory() as work:
            now = self.clock()
            job = work.session.scalar(
                select(ProcessingJob)
                .where(
                    ProcessingJob.source_type == JobSourceType.FILE,
                    or_(
                        ProcessingJob.status == JobStatus.PENDING,
                        (ProcessingJob.status == JobStatus.RUNNING)
                        & (
                            or_(
                                ProcessingJob.lease_expires_at < now,
                                ProcessingJob.lease_expires_at.is_(None),
                            )
                        ),
                    ),
                )
                .order_by(ProcessingJob.created_at, ProcessingJob.id)
                .with_for_update(skip_locked=True)
                .limit(1)
            )
            if job is None:
                return None
            job.status, job.started_at = JobStatus.RUNNING, job.started_at or now
            job.lease_token = uuid.uuid4()
            job.attempts += 1
            job.heartbeat_at, job.lease_expires_at = now, now + timedelta(seconds=60)
            work.commit()
            work.session.expunge(job)
            return job

    def checkpoint(self, job_id, token, processed=None, sampled=None):
        with self.factory() as work:
            job = self.row(work, job_id, lock=True)
            if job.status != JobStatus.RUNNING or job.lease_token != token:
                return False
            camera = work.session.get(Camera, job.camera_id)
            if (
                job.cancel_requested
                or camera.status != CameraStatus.ACTIVE
                or not camera.ai_enabled
            ):
                return False
            if processed is not None:
                job.processed_frames, job.sampled_frames = processed, sampled
                if job.total_frames is not None and processed > job.total_frames:
                    job.total_frames = None  # Container frame count was only a hint.
            job.heartbeat_at = self.clock()
            job.lease_expires_at = self.clock() + timedelta(seconds=60)
            work.commit()
            return True

    def finish(self, job_id, token, status, error_code=None):
        source = None
        with self.factory() as work:
            job = self.row(work, job_id, lock=True)
            if job.status != JobStatus.RUNNING or job.lease_token != token:
                return
            camera = work.session.get(Camera, job.camera_id)
            if (
                job.cancel_requested
                or camera.status != CameraStatus.ACTIVE
                or not camera.ai_enabled
            ):
                status, error_code = JobStatus.CANCELLED, None
            job.status, job.ended_at = status, self.clock()
            job.error_code = error_code
            job.error_message = (
                "Không xử lý được video. Kiểm tra cấu hình worker và dịch vụ lưu trữ."
                if error_code
                else None
            )
            job.lease_expires_at = None
            if status == JobStatus.SUCCEEDED:
                job.total_frames = job.processed_frames
            self.audit(work, AuditEvent.JOB_FINISHED, job)
            source = job.source_ref
            work.commit()
        if source:
            self.staging.remove(source)

    def cleanup(self):
        """Reconcile terminal staging files and orphaned uploads after a 24h grace period."""
        if not self.staging.root.exists():
            return
        with self.factory() as work:
            live = set(
                work.session.scalars(
                    select(ProcessingJob.source_ref).where(ProcessingJob.status.not_in(TERMINAL))
                )
            )
            terminal = set(
                work.session.scalars(
                    select(ProcessingJob.source_ref).where(ProcessingJob.status.in_(TERMINAL))
                )
            )
        for path in self.staging.root.iterdir():
            if path.is_file() and not path.is_symlink() and path.name not in live:
                if path.name in terminal or path.stat().st_mtime < self.clock().timestamp() - 86400:
                    if re.fullmatch(r"[0-9a-f]{32}\.(mp4|mkv|avi)", path.name):
                        self.staging.remove(path.name)
