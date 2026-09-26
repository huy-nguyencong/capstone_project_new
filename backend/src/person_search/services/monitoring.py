from __future__ import annotations

import io
import math
import time
import uuid
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Any

from PIL import Image, ImageDraw
from sqlalchemy import func, select

from person_search.api.errors import ApiError
from person_search.services.searches import EncoderUnavailableError
from person_search.storage.postgres.models import (
    Area,
    Camera,
    CameraStatus,
    JobStatus,
    ProcessingJob,
    RtspStatus,
    WorkerHeartbeat,
)
from person_search.workers.contracts import SampledFrame, SourceFrame
from person_search.workers.pipeline import Pipeline

TERMINAL_JOBS = (JobStatus.SUCCEEDED, JobStatus.FAILED, JobStatus.CANCELLED)
PROBE_TEXT = "A person walking."
TRACKER_WARMUP_FRAMES = 5
HEARTBEAT_STALE_AFTER = timedelta(seconds=45)
RTSP_STATUS_STALE_AFTER = timedelta(minutes=5)
JOB_METRICS_STALE_AFTER = timedelta(seconds=30)
ERROR_WINDOW = timedelta(hours=24)
MAX_WORKER_INSTANCES = 10
CAMERA_METRIC_KEYS = (
    "source_fps",
    "sampled_fps",
    "detector_ms",
    "tracker_ms",
    "encoder_ms",
    "queue_ms",
    "track_count",
    "rss_bytes",
    "cpu_percent",
)


class Outcome(StrEnum):
    SUCCESS = "SUCCESS"
    INCONCLUSIVE = "INCONCLUSIVE"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"


class WorkerState(StrEnum):
    IDLE = "IDLE"
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    ERROR = "ERROR"
    DISABLED = "DISABLED"
    OFFLINE = "OFFLINE"


@dataclass(frozen=True, slots=True)
class Step:
    component: str
    label: str
    outcome: Outcome
    message: str | None = None
    duration_ms: int | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "component": self.component,
            "label": self.label,
            "outcome": self.outcome.value,
            "message": self.message,
            "duration_ms": self.duration_ms,
        }


def _utc_now() -> datetime:
    return datetime.now(UTC)


def iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def freshness(
    observed_at: datetime | None, now: datetime, max_age: timedelta
) -> dict[str, Any]:
    if observed_at is None:
        return {"observed_at": None, "age_seconds": None, "stale": True}
    if observed_at.tzinfo is None:
        observed_at = observed_at.replace(tzinfo=UTC)
    age = max((now - observed_at).total_seconds(), 0.0)
    return {
        "observed_at": iso(observed_at),
        "age_seconds": round(age, 1),
        "stale": age > max_age.total_seconds(),
    }


def worker_alive(heartbeat: Any | None, now: datetime) -> bool:
    if heartbeat is None or heartbeat.state == "STOPPED":
        return False
    return not freshness(heartbeat.heartbeat_at, now, HEARTBEAT_STALE_AFTER)["stale"]


def camera_metrics(
    job: Any | None, failed_jobs: int, now: datetime, *, live: bool
) -> dict[str, Any]:
    values = dict(getattr(job, "metrics", None) or {}) if job is not None else {}
    metrics: dict[str, Any] = {key: values.get(key) for key in CAMERA_METRIC_KEYS}
    detector, tracker = values.get("detector_ms"), values.get("tracker_ms")
    metrics["processed_fps"] = values.get("sampled_fps")
    metrics["latency_ms"] = (
        round(detector + tracker, 3) if detector is not None and tracker is not None else None
    )
    metrics["retries"] = values.get("error_count")
    metrics["error_count"] = failed_jobs
    updated = getattr(job, "metrics_updated_at", None) if job is not None else None
    metrics["live"] = live and updated is not None
    metrics["freshness"] = freshness(updated, now, JOB_METRICS_STALE_AFTER)
    return metrics


def overall(steps: Sequence[Step]) -> Outcome:
    outcomes = {step.outcome for step in steps}
    if Outcome.FAILED in outcomes:
        return Outcome.FAILED
    if Outcome.INCONCLUSIVE in outcomes:
        return Outcome.INCONCLUSIVE
    return Outcome.SUCCESS


def connection_state(camera: Any) -> str:
    if not camera.rtsp_url:
        return "NOT_CONFIGURED"
    return camera.rtsp_status.value


def worker_state(
    camera: Any,
    active_job: Any | None,
    last_job: Any | None,
    now: datetime,
    *,
    alive: bool = True,
) -> tuple[WorkerState, str | None]:
    if not camera.ai_enabled:
        return WorkerState.DISABLED, None
    if active_job is not None and active_job.status is JobStatus.RUNNING:
        if getattr(active_job, "error_code", None):
            return WorkerState.QUEUED, active_job.error_code
        if active_job.lease_expires_at is not None and active_job.lease_expires_at < now:
            return WorkerState.ERROR, "worker_heartbeat_lost"
        return WorkerState.RUNNING, None
    if active_job is not None:
        return WorkerState.QUEUED, None if alive else "worker_offline"
    if last_job is not None and last_job.status is JobStatus.FAILED:
        return WorkerState.ERROR, last_job.error_code or "job_failed"
    return WorkerState.IDLE, None


def camera_category(
    camera: Any, connection: str, state: WorkerState, error: str | None = None
) -> str:
    if state in (WorkerState.ERROR, WorkerState.OFFLINE) or error == "worker_offline":
        return "ai_issues"
    if connection in (RtspStatus.OFFLINE.value, RtspStatus.ERROR.value):
        return "connection_issues"
    if camera.status is not CameraStatus.ACTIVE or connection == RtspStatus.UNKNOWN.value:
        return "unknown"
    return "healthy"


def synthetic_frame() -> SourceFrame:
    image = Image.new("RGB", (640, 360), (72, 72, 72))
    ImageDraw.Draw(image).rectangle((280, 90, 360, 300), fill=(180, 40, 40))
    return SourceFrame(
        camera_id=uuid.UUID("00000000-0000-4000-8000-000000000000"),
        source_frame_index=0,
        source_timestamp_ms=0,
        image=image,
        width=640,
        height=360,
    )


def check_embedding(values: Sequence[float], dimension: int) -> str | None:
    if len(values) != dimension:
        return f"Embedding có {len(values)} chiều, cấu hình yêu cầu {dimension}."
    if not all(math.isfinite(value) for value in values):
        return "Embedding chứa giá trị không hợp lệ."
    if not math.isclose(math.sqrt(sum(v * v for v in values)), 1.0, abs_tol=1e-3):
        return "Embedding chưa được chuẩn hóa L2."
    return None


class _Timer:
    def __enter__(self) -> _Timer:
        self.start = time.perf_counter()
        self.ms = 0
        return self

    def __exit__(self, *args: object) -> None:
        self.ms = round((time.perf_counter() - self.start) * 1000)


def run_pipeline_steps(
    camera: Any,
    config: Any | None,
    probe: Callable[[str, str | None], str],
    pipeline_factory: Callable[[Any], Pipeline] | None,
) -> list[Step]:
    steps: list[Step] = []
    detector_label = (
        f"Detector · {config.detector_name} {config.detector_version}" if config else "Detector"
    )
    tracker_label = (
        f"Tracker · {config.tracker_name} {config.tracker_version}" if config else "Tracker"
    )
    encoder_label = (
        f"Image Encoder · {config.encoder_name} {config.encoder_version}"
        if config
        else "Image Encoder"
    )
    rest = [
        ("DETECTOR", detector_label),
        ("TRACKER", tracker_label),
        ("IMAGE_ENCODER", encoder_label),
    ]

    def skip_rest(reason: str, start: int = 0) -> list[Step]:
        return steps + [
            Step(component, label, Outcome.SKIPPED, reason) for component, label in rest[start:]
        ]

    if camera.status is not CameraStatus.ACTIVE:
        steps.append(
            Step("FRAME_SOURCE", "Nguồn khung hình", Outcome.FAILED, "Camera không hoạt động.")
        )
        return skip_rest("Bỏ qua vì nguồn khung hình lỗi.")
    if not camera.ai_enabled:
        steps.append(
            Step("FRAME_SOURCE", "Nguồn khung hình", Outcome.FAILED, "Camera chưa bật xử lý AI.")
        )
        return skip_rest("Bỏ qua vì camera chưa bật xử lý AI.")
    if camera.rtsp_url:
        with _Timer() as timer:
            try:
                status = probe(camera.rtsp_url, camera.rtsp_credentials)
                message = {
                    "ONLINE": "Kết nối RTSP thành công.",
                    "OFFLINE": "Không nhận được luồng RTSP.",
                    "ERROR": "Không chạy được ffprobe trên máy chủ.",
                }[status]
            except ApiError as error:
                status, message = "ERROR", error.message
        outcome = Outcome.SUCCESS if status == "ONLINE" else Outcome.FAILED
        steps.append(Step("FRAME_SOURCE", "Nhận khung hình RTSP", outcome, message, timer.ms))
        if outcome is Outcome.FAILED:
            return skip_rest("Bỏ qua vì nguồn khung hình lỗi.")
    else:
        steps.append(
            Step(
                "FRAME_SOURCE",
                "Nguồn khung hình",
                Outcome.SKIPPED,
                "Camera dùng video tải lên; kiểm tra mô hình bằng khung hình tổng hợp.",
            )
        )
    if config is None:
        steps.append(
            Step("DETECTOR", detector_label, Outcome.FAILED, "Chưa có cấu hình AI đang áp dụng.")
        )
        return skip_rest("Bỏ qua vì chưa có cấu hình AI.", 1)
    if pipeline_factory is None:
        steps.append(
            Step(
                "DETECTOR",
                detector_label,
                Outcome.FAILED,
                "Máy chủ chưa cấu hình pipeline diagnostics.",
            )
        )
        return skip_rest("Bỏ qua vì chưa có pipeline diagnostics.", 1)
    try:
        pipeline = pipeline_factory(config)
    except ValueError:
        steps.append(
            Step(
                "DETECTOR",
                detector_label,
                Outcome.FAILED,
                "Máy chủ chưa có adapter cho cấu hình AI đang áp dụng.",
            )
        )
        return skip_rest("Bỏ qua vì không nạp được mô hình.", 1)

    frame = synthetic_frame()
    sampled_frame = SampledFrame(frame, sampling_interval=10, sample_sequence=0)
    try:
        with _Timer() as timer:
            try:
                boxes = pipeline.detector.detect(sampled_frame)
            except Exception:
                steps.append(Step("DETECTOR", detector_label, Outcome.FAILED, "Detector lỗi."))
                return skip_rest("Bỏ qua vì Detector lỗi.", 1)
        if not boxes:
            steps.append(
                Step(
                    "DETECTOR",
                    detector_label,
                    Outcome.INCONCLUSIVE,
                    "Khung hình kiểm tra không có người.",
                    timer.ms,
                )
            )
            return skip_rest("Chưa có vùng người để kiểm tra.", 1)
        steps.append(
            Step(
                "DETECTOR",
                detector_label,
                Outcome.SUCCESS,
                f"{len(boxes)} vùng phát hiện trên khung {frame.image.width}×{frame.image.height}.",
                timer.ms,
            )
        )
        with _Timer() as timer:
            try:
                tracks = []
                for index in range(TRACKER_WARMUP_FRAMES):
                    warmup_source = SourceFrame(
                        camera_id=frame.camera_id,
                        source_frame_index=index * 10,
                        source_timestamp_ms=index * 400,
                        image=frame.image,
                        width=frame.width,
                        height=frame.height,
                    )
                    warmup = SampledFrame(warmup_source, 10, index)
                    tracks += pipeline.tracker.update(warmup, boxes)
                tracks += pipeline.tracker.finish()
            except Exception:
                steps.append(Step("TRACKER", tracker_label, Outcome.FAILED, "Tracker lỗi."))
                return skip_rest("Bỏ qua vì Tracker lỗi.", 2)
        if not tracks:
            steps.append(
                Step(
                    "TRACKER",
                    tracker_label,
                    Outcome.INCONCLUSIVE,
                    "Chưa hình thành track để xác minh.",
                    timer.ms,
                )
            )
            return skip_rest("Chưa có track để mã hóa.", 2)
        steps.append(
            Step("TRACKER", tracker_label, Outcome.SUCCESS, f"{len(tracks)} track.", timer.ms)
        )
        box = tracks[0].bbox
        crop = frame.image.crop((box.x, box.y, box.x + box.width, box.y + box.height))
        with _Timer() as timer:
            try:
                embedding = pipeline.encoder.encode(crop)
                problem = check_embedding(embedding, config.encoder_dimension)
            except Exception:
                problem = "Image Encoder lỗi."
        steps.append(
            Step(
                "IMAGE_ENCODER",
                encoder_label,
                Outcome.FAILED if problem else Outcome.SUCCESS,
                problem or f"Embedding {config.encoder_dimension} chiều.",
                timer.ms,
            )
        )
    finally:
        pipeline.tracker.close()
    return steps


def _probe_image() -> bytes:
    output = io.BytesIO()
    synthetic_frame().image.save(output, format="JPEG", quality=85)
    return output.getvalue()


class MonitoringService:
    def __init__(
        self,
        unit_of_work_factory: Callable[[], Any],
        *,
        health: Any,
        search: Any,
        runtime: Any,
        pipeline_factory: Callable[[Any], Pipeline] | None = None,
        clock: Callable[[], datetime] = _utc_now,
    ) -> None:
        self._factory = unit_of_work_factory
        self._health = health
        self._search = search
        self._runtime = runtime
        self._pipeline_factory = pipeline_factory
        self._clock = clock

    def system_status(self) -> dict[str, Any]:
        now = self._clock()
        with self._factory() as work:
            session = work.session
            cameras = session.execute(
                select(Camera, Area)
                .join(Area, Area.id == Camera.area_id)
                .where(Camera.status != CameraStatus.RETIRED)
                .order_by(Camera.name, Camera.id)
            ).all()
            active_jobs = list(
                session.scalars(
                    select(ProcessingJob)
                    .where(ProcessingJob.status.in_((JobStatus.PENDING, JobStatus.RUNNING)))
                    .order_by(ProcessingJob.created_at, ProcessingJob.id)
                )
            )
            last_jobs = {
                job.camera_id: job
                for job in session.scalars(
                    select(ProcessingJob)
                    .where(ProcessingJob.status.in_(TERMINAL_JOBS))
                    .distinct(ProcessingJob.camera_id)
                    .order_by(ProcessingJob.camera_id, ProcessingJob.updated_at.desc())
                )
            }
            failed_counts = dict(
                session.execute(
                    select(ProcessingJob.camera_id, func.count())
                    .where(
                        ProcessingJob.status == JobStatus.FAILED,
                        ProcessingJob.updated_at >= now - ERROR_WINDOW,
                    )
                    .group_by(ProcessingJob.camera_id)
                ).all()
            )
            heartbeats = list(
                session.scalars(
                    select(WorkerHeartbeat)
                    .order_by(WorkerHeartbeat.heartbeat_at.desc())
                    .limit(MAX_WORKER_INSTANCES)
                )
            )
            last_job_heartbeat = session.scalar(select(func.max(ProcessingJob.heartbeat_at)))
            alive = any(worker_alive(row, now) for row in heartbeats)
            items = self._camera_rows(
                cameras, active_jobs, last_jobs, failed_counts, now, alive=alive
            )
        summary = {"healthy": 0, "connection_issues": 0, "ai_issues": 0, "unknown": 0}
        for item in items:
            summary[item["category"]] += 1
        storage = self._storage()
        encoder = self._encoder_status()
        worker = self._worker(active_jobs, heartbeats, last_job_heartbeat, now, alive)
        return {
            "generated_at": iso(now),
            "summary": summary,
            "cameras": items,
            "storage": storage,
            "encoder": encoder,
            "worker": worker,
            "components": [
                *(
                    {"component": f"STORAGE_{name.upper()}", "state": state, "checked_at": iso(now)}
                    for name, state in storage.items()
                ),
                {"component": "SEARCH_ENCODER", "state": encoder, "checked_at": iso(now)},
                {
                    "component": "AI_WORKER",
                    "state": worker["state"],
                    "checked_at": worker["freshness"]["observed_at"],
                },
            ],
        }

    def _worker(self, active_jobs, heartbeats, last_job_heartbeat, now, alive) -> dict[str, Any]:
        running = [job for job in active_jobs if job.status is JobStatus.RUNNING]
        pending = [job for job in active_jobs if job.status is JobStatus.PENDING]
        processing = [job for job in running if not getattr(job, "error_code", None)]
        waiting = len(pending) + len(running) - len(processing)
        lease_lost = any(
            job.lease_expires_at is not None and job.lease_expires_at < now for job in processing
        )
        if lease_lost:
            state = WorkerState.ERROR
        elif not alive:
            state = WorkerState.OFFLINE
        elif processing:
            state = WorkerState.RUNNING
        elif waiting:
            state = WorkerState.QUEUED
        else:
            state = WorkerState.IDLE
        latest = heartbeats[0] if heartbeats else None
        observed = latest.heartbeat_at if latest is not None else None
        oldest = min((job.created_at for job in pending), default=None)
        return {
            "state": state.value,
            "queue_depth": len(pending),
            "retry_waiting": len(running) - len(processing),
            "oldest_queued_at": iso(oldest),
            "last_heartbeat_at": iso(observed or last_job_heartbeat),
            "last_job_heartbeat_at": iso(last_job_heartbeat),
            "freshness": freshness(observed, now, HEARTBEAT_STALE_AFTER),
            "instances": [
                {
                    "id": row.worker_id,
                    "state": row.state,
                    "alive": worker_alive(row, now),
                    "current_job_id": str(row.current_job_id) if row.current_job_id else None,
                    "started_at": iso(row.started_at),
                    "state_changed_at": iso(row.state_changed_at),
                    "rss_bytes": row.rss_bytes,
                    "cpu_percent": row.cpu_percent,
                    "freshness": freshness(row.heartbeat_at, now, HEARTBEAT_STALE_AFTER),
                }
                for row in heartbeats
            ],
        }

    def _camera_rows(
        self, cameras, active_jobs, last_jobs, failed_counts, now, *, alive: bool = True
    ) -> list[dict[str, Any]]:
        by_camera: dict[uuid.UUID, ProcessingJob] = {}
        for job in active_jobs:
            current = by_camera.get(job.camera_id)
            if current is None or (
                job.status is JobStatus.RUNNING and current.status is not JobStatus.RUNNING
            ):
                by_camera[job.camera_id] = job
        items = []
        for camera, area in cameras:
            active = by_camera.get(camera.id)
            last = last_jobs.get(camera.id)
            state, error = worker_state(camera, active, last, now, alive=alive)
            connection = connection_state(camera)
            heartbeat = active.heartbeat_at if active is not None else None
            running = active is not None and active.status is JobStatus.RUNNING
            metrics_job = active if running else last
            items.append(
                {
                    "id": str(camera.id),
                    "code": camera.code,
                    "name": camera.name,
                    "area_name": area.name,
                    "status": camera.status.value,
                    "connection": connection,
                    "connection_freshness": (
                        freshness(camera.last_checked_at, now, RTSP_STATUS_STALE_AFTER)
                        if camera.rtsp_url
                        else None
                    ),
                    "last_checked_at": iso(camera.last_checked_at),
                    "ai_enabled": camera.ai_enabled,
                    "worker_state": state.value,
                    "active_job_id": str(active.id) if active is not None else None,
                    "active_job_status": active.status.value if active is not None else None,
                    "last_job_status": last.status.value if last is not None else None,
                    "last_job_ended_at": iso(last.ended_at) if last is not None else None,
                    "last_heartbeat_at": iso(heartbeat),
                    "heartbeat_freshness": (
                        freshness(heartbeat, now, HEARTBEAT_STALE_AFTER)
                        if running
                        else None
                    ),
                    "last_error": error,
                    "metrics": camera_metrics(
                        metrics_job,
                        int(failed_counts.get(camera.id, 0)),
                        now,
                        live=running,
                    ),
                    "category": camera_category(camera, connection, state, error),
                }
            )
        return items

    def _storage(self) -> dict[str, str]:
        report = self._health.check()
        return {
            name: "UP" if values.get("status") == "ok" else "DOWN"
            for name, values in report.components.items()
        }

    def _encoder_status(self) -> str:
        try:
            config = self._search.active_config()
            self._search.gateway(config.encoder_version)
            return "UP"
        except EncoderUnavailableError:
            return "DOWN"

    def camera_pipeline(self, camera_id: uuid.UUID) -> dict[str, Any]:
        with self._factory() as work:
            camera = work.repositories.cameras.get(camera_id)
            if camera is None:
                raise ApiError(404, "camera_not_found", "Không tìm thấy camera.")
            config = work.repositories.ai_configs.active()
        steps = run_pipeline_steps(camera, config, self._runtime.probe, self._pipeline_factory)
        return self._report(steps)

    def search_components(self) -> dict[str, Any]:
        steps: list[Step] = []
        try:
            config = self._search.active_config()
        except EncoderUnavailableError:
            steps.append(
                Step("ACTIVE_CONFIG", "Cấu hình encoder", Outcome.FAILED, "Chưa có cấu hình AI.")
            )
            steps += [
                Step(component, label, Outcome.SKIPPED, "Bỏ qua vì chưa có cấu hình AI.")
                for component, label in (
                    ("TEXT_ENCODER", "Text Encoder"),
                    ("IMAGE_ENCODER", "Image Encoder"),
                )
            ]
        else:
            name = f"{config.encoder_name} {config.encoder_version}"
            steps.append(
                Step(
                    "ACTIVE_CONFIG",
                    "Cấu hình encoder",
                    Outcome.SUCCESS,
                    f"{name} · {config.encoder_dimension} chiều.",
                )
            )
            steps.append(
                self._encode_step(
                    "TEXT_ENCODER",
                    f"Text Encoder · {name}",
                    config,
                    lambda gateway: gateway.text(
                        PROBE_TEXT,
                        version=config.encoder_version,
                        dimension=config.encoder_dimension,
                    ),
                )
            )
            steps.append(
                self._encode_step(
                    "IMAGE_ENCODER",
                    f"Image Encoder · {name}",
                    config,
                    lambda gateway: gateway.image(
                        _probe_image(),
                        version=config.encoder_version,
                        dimension=config.encoder_dimension,
                    ),
                )
            )
        labels = {"postgres": "PostgreSQL", "milvus": "Milvus", "minio": "MinIO"}
        for name, state in self._storage().items():
            steps.append(
                Step(
                    f"STORAGE_{name.upper()}",
                    labels.get(name, name),
                    Outcome.SUCCESS if state == "UP" else Outcome.FAILED,
                    "Kết nối được." if state == "UP" else "Không kết nối được.",
                )
            )
        return self._report(steps)

    def _encode_step(self, component: str, label: str, config: Any, call) -> Step:
        with _Timer() as timer:
            try:
                embedding = call(self._search.gateway(config.encoder_version))
                problem = check_embedding(embedding, config.encoder_dimension)
            except EncoderUnavailableError:
                problem = "Encoder không khả dụng."
        return Step(
            component,
            label,
            Outcome.FAILED if problem else Outcome.SUCCESS,
            problem or f"Embedding {config.encoder_dimension} chiều.",
            timer.ms,
        )

    def _report(self, steps: list[Step]) -> dict[str, Any]:
        return {
            "ran_at": iso(self._clock()),
            "overall": overall(steps).value,
            "steps": [step.as_dict() for step in steps],
        }
