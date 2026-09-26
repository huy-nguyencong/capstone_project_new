"""Transactional camera administration and global model configuration."""

import base64
import os
import uuid
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import select, text

from person_search.ai.configuration import ConfigApplyCoordinator
from person_search.ai.registry import (
    IncompatibleModelPairError,
    ModelNotFoundError,
    ModelRegistry,
    ModelUnavailableError,
    load_registry,
)
from person_search.api.errors import ApiError
from person_search.services.audit import AuditEvent, record_audit
from person_search.storage.postgres.errors import DuplicateEntityError
from person_search.storage.postgres.models import (
    AIConfigStatus,
    AIConfigVersion,
    Area,
    AuditResult,
    Camera,
    CameraStatus,
    JobStatus,
    ProcessingJob,
    RtspStatus,
)


def iso(value):
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z") if value else None


def identifier(value):
    try:
        return uuid.UUID(str(value))
    except ValueError:
        raise ApiError(422, "invalid_id", "ID không hợp lệ.") from None


def required(value, limit):
    if not isinstance(value, str) or not value.strip() or len(value.strip()) > limit:
        raise ApiError(422, "invalid_field", "Trường bắt buộc bị trống hoặc quá dài.")
    return value.strip()


class CameraService:
    def __init__(
        self,
        factory,
        runtime,
        registry: ModelRegistry | None = None,
        apply_config=None,
        config_loader=None,
    ):
        self.factory = factory
        self.runtime = runtime
        if registry is not None and not isinstance(registry, ModelRegistry):
            raise TypeError("registry must be a validated ModelRegistry.")
        self.registry = registry or ModelRegistry.empty()
        self.apply_config = apply_config or (lambda config: None)
        self.config_coordinator = ConfigApplyCoordinator(
            self.registry,
            loader=config_loader or (lambda config, _selection: self.apply_config(config)),
        )

    @staticmethod
    def registry_from_environment(
        deployment_environment: str | None = None,
    ) -> ModelRegistry | None:
        path = os.getenv("PERSON_SEARCH_MODEL_REGISTRY")
        if not path:
            return None
        artifact_root = os.getenv("PERSON_SEARCH_MODEL_ARTIFACT_ROOT")
        environment = (
            deployment_environment or os.getenv("PERSON_SEARCH_ENV", "development")
        ).lower()
        allow_demo = (
            environment in {"development", "testing"}
            and os.getenv("PERSON_SEARCH_ALLOW_DEMO_MODELS") == "1"
        )
        return load_registry(
            path,
            artifact_root=artifact_root or Path(path).resolve().parent,
            allow_demo=allow_demo,
            preflight_available=(
                {"yolo11n_coco", "bytetrack_v1", "rasa_cuhk_pedes_v1"}
                if not allow_demo
                else ()
            ),
        )

    def models(self):
        return self.registry.public_catalog()

    def view(self, work, camera):
        area = work.session.get(Area, camera.area_id)
        url = camera.rtsp_url
        if url and (camera.rtsp_credentials or camera.rtsp_secret_ref):
            scheme, tail = url.split("://", 1)
            url = scheme + "://***@" + tail
        return dict(
            id=str(camera.id),
            code=camera.code,
            name=camera.name,
            area=dict(id=str(area.id), code=area.code, name=area.name),
            status=camera.status.value,
            rtsp_status=camera.rtsp_status.value,
            rtsp_url_masked=url,
            has_rtsp=bool(camera.rtsp_url),
            ai_enabled=camera.ai_enabled,
            version=camera.version,
            last_checked_at=iso(camera.last_checked_at),
        )

    def camera(self, work, camera_id, lock=False):
        query = select(Camera).where(Camera.id == identifier(camera_id))
        if lock:
            query = query.with_for_update()
        row = work.session.scalar(query)
        if row is None:
            raise ApiError(404, "camera_not_found", "Không tìm thấy camera.")
        return row

    def audit(self, work, actor, event, target, success=True):
        with work.session.no_autoflush:
            actor_row = work.repositories.users.get(actor)
        record_audit(
            work.repositories,
            event_type=event,
            result=AuditResult.SUCCESS if success else AuditResult.FAILURE,
            target_type="camera" if event.value.startswith("camera.") else "ai",
            target_id=target,
            actor=actor_row,
        )

    def list(self, args):
        try:
            limit = int(args.get("limit", 20))
            if not 1 <= limit <= 100:
                raise ValueError
            query = select(Camera).order_by(Camera.id)
            if args.get("area_id"):
                query = query.where(Camera.area_id == identifier(args["area_id"]))
            if args.get("status"):
                query = query.where(Camera.status == CameraStatus(args["status"]))
            if args.get("cursor"):
                raw = base64.b64decode(args["cursor"], altchars=b"-_", validate=True)
                query = query.where(Camera.id > uuid.UUID(bytes=raw))
        except (ValueError, TypeError):
            raise ApiError(422, "invalid_filter", "Bộ lọc hoặc cursor không hợp lệ.") from None
        with self.factory() as work:
            rows = list(work.session.scalars(query.limit(limit + 1)))
            return dict(
                items=[self.view(work, r) for r in rows[:limit]],
                next_cursor=base64.urlsafe_b64encode(rows[limit - 1].id.bytes).decode()
                if len(rows) > limit
                else None,
            )

    def get(self, camera_id):
        with self.factory() as work:
            return self.view(work, self.camera(work, camera_id))

    def save(self, body, actor, camera_id=None):
        allowed = (
            {"name", "rtsp_url", "version"}
            if camera_id
            else {"code", "name", "area_id", "rtsp_url"}
        )
        if camera_id and "area_id" in body:
            raise ApiError(422, "camera_area_immutable", "Không thể thay đổi khu vực camera.")
        if body.keys() - allowed:
            raise ApiError(422, "unknown_fields", "Có trường không được hỗ trợ.")
        with self.factory() as work:
            if camera_id:
                row = self.camera(work, camera_id, True)
                if type(body.get("version")) is not int or row.version != body["version"]:
                    raise ApiError(409, "version_conflict", "Camera đã thay đổi. Hãy tải lại.")
                if row.status != CameraStatus.ACTIVE:
                    raise ApiError(409, "camera_not_active", "Camera đã ngừng vận hành.")
                row.version += 1
            else:
                area_id = identifier(body.get("area_id"))
                if work.session.get(Area, area_id) is None:
                    raise ApiError(422, "area_not_found", "Không tìm thấy khu vực.")
                row = Camera(
                    id=uuid.uuid4(),
                    code=required(body.get("code"), 50).upper(),
                    area_id=area_id,
                    status=CameraStatus.ACTIVE,
                    rtsp_status=RtspStatus.UNKNOWN,
                    ai_enabled=False,
                    version=1,
                )
                work.session.add(row)
            if not camera_id or "name" in body:
                row.name = required(body.get("name"), 200)
            if "rtsp_url" in body:
                row.rtsp_url, row.rtsp_credentials = self.runtime.split_url(body["rtsp_url"])
                row.rtsp_secret_ref = None
                row.rtsp_status = RtspStatus.UNKNOWN
                row.last_checked_at = None
            self.audit(
                work,
                actor,
                AuditEvent.CAMERA_UPDATED if camera_id else AuditEvent.CAMERA_CREATED,
                row.id,
            )
            try:
                work.commit()
            except DuplicateEntityError:
                raise ApiError(409, "camera_code_taken", "Mã camera đã tồn tại.") from None
            return self.view(work, row)

    def transition(self, camera_id, actor, enabled=None):
        with self.factory() as work:
            row = self.camera(work, camera_id, True)
            if enabled is not None:
                if row.status != CameraStatus.ACTIVE:
                    raise ApiError(409, "camera_not_active", "Camera đã ngừng vận hành.")
                if enabled and not self.active(work):
                    raise ApiError(409, "ai_config_missing", "Chưa có cấu hình AI.")
                changed = row.ai_enabled != enabled
                row.ai_enabled = enabled
            else:
                changed = row.status != CameraStatus.RETIRED or row.ai_enabled
                row.status, row.ai_enabled = CameraStatus.RETIRED, False
            if changed:
                if enabled is False or enabled is None:
                    now = datetime.now(UTC)
                    jobs = work.session.scalars(
                        select(ProcessingJob).where(
                            ProcessingJob.camera_id == row.id,
                            ProcessingJob.status.in_((JobStatus.PENDING, JobStatus.RUNNING)),
                        )
                    )
                    for job in jobs:
                        job.cancel_requested = True
                        if job.status is JobStatus.PENDING:
                            job.status = JobStatus.CANCELLED
                            job.ended_at = now
                row.version += 1
                self.audit(
                    work,
                    actor,
                    AuditEvent.AI_STATE_CHANGED
                    if enabled is not None
                    else AuditEvent.CAMERA_DEACTIVATED,
                    row.id,
                )
                work.commit()
            return self.view(work, row)

    def test(self, camera_id, actor):
        # Network I/O outside the row lock; reject a stale result if URL changed meanwhile.
        with self.factory() as work:
            row = self.camera(work, camera_id)
            url, secret, version = row.rtsp_url, row.rtsp_credentials, row.version
            if not url:
                raise ApiError(422, "camera_has_no_rtsp", "Camera không có RTSP.")
            if row.rtsp_secret_ref and not secret:
                raise ApiError(503, "secret_store_unavailable", "Cần cập nhật thông tin RTSP.")
        status = self.runtime.probe(url, secret)
        with self.factory() as work:
            row = self.camera(work, camera_id, True)
            if row.version != version:
                raise ApiError(409, "version_conflict", "Camera đã thay đổi trong lúc kiểm tra.")
            row.rtsp_status, row.last_checked_at = RtspStatus(status), datetime.now(UTC)
            row.version += 1
            self.audit(work, actor, AuditEvent.CAMERA_CONNECTION_TESTED, row.id, status == "ONLINE")
            work.commit()
            return dict(
                rtsp_status=status,
                checked_at=iso(row.last_checked_at),
                message={
                    "ONLINE": "Kết nối thành công.",
                    "OFFLINE": "Không kết nối được RTSP.",
                    "ERROR": "Không chạy được ffprobe trên máy chủ.",
                }[status],
            )

    def active(self, work):
        return work.session.scalar(
            select(AIConfigVersion).where(AIConfigVersion.status == AIConfigStatus.ACTIVE)
        )

    def config_view(self, row):
        return dict(
            detector_id=row.detector_name if row else None,
            tracker_id=row.tracker_name if row else None,
            version=row.version if row else None,
            applied_at=iso(row.created_at) if row else None,
        )

    def config(self):
        with self.factory() as work:
            return self.config_view(self.active(work))

    def configure(self, body, actor):
        try:
            return self._configure(body, actor)
        except ApiError as error:
            if error.code == "model_apply_failed":
                with self.factory() as work:
                    self.audit(work, actor, AuditEvent.AI_CONFIG_FAILED, None, False)
                    work.commit()
            raise

    def _configure(self, body, actor):
        if set(body) != {"detector_id", "tracker_id", "version"}:
            raise ApiError(422, "invalid_config", "Cần detector_id, tracker_id và version.")
        if not isinstance(body["detector_id"], str) or not isinstance(body["tracker_id"], str):
            raise ApiError(422, "model_unavailable", "Mô hình chưa khả dụng.")
        try:
            selection = self.registry.resolve(body["detector_id"], body["tracker_id"])
        except (ModelNotFoundError, ModelUnavailableError):
            raise ApiError(422, "model_unavailable", "Mô hình chưa khả dụng.") from None
        except IncompatibleModelPairError:
            raise ApiError(
                422, "incompatible_model_pair", "Detector và Tracker không tương thích."
            ) from None
        detector, tracker, encoder = (
            selection.detector,
            selection.tracker,
            selection.encoder,
        )
        with self.factory() as work:
            # Also serialize the initial apply when no active row exists yet.
            work.session.execute(text("SELECT pg_advisory_xact_lock(734201)"))
            old = self.active(work)
            if body["version"] != (old.version if old else None):
                raise ApiError(409, "version_conflict", "Cấu hình đã thay đổi. Hãy tải lại.")
            row = AIConfigVersion(
                id=uuid.uuid4(),
                version=str(uuid.uuid4()),
                detector_name=detector.id,
                detector_version=detector.version,
                tracker_name=tracker.id,
                tracker_version=tracker.version,
                encoder_name=encoder.id,
                encoder_version=encoder.version,
                encoder_dimension=encoder.dimension,
                checkpoint_sha256=encoder.artifact.sha256,
                status=AIConfigStatus.ACTIVE,
            )
            self.audit(work, actor, AuditEvent.AI_CONFIG_REQUESTED, row.id)
            try:
                prepared = self.config_coordinator.prepare(row)
            except Exception:
                raise ApiError(
                    503, "model_apply_failed", "Không áp dụng được cấu hình; giữ cấu hình cũ."
                ) from None
            if old:
                old.status = AIConfigStatus.RETIRED
                work.flush()
            work.session.add(row)
            self.audit(work, actor, AuditEvent.AI_CONFIG_APPLIED, row.id)
            work.commit()
            self.config_coordinator.activate(prepared)
            return self.config_view(row)
