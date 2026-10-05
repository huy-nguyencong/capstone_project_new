from __future__ import annotations

import io
import math
import os
import threading
import time
from collections.abc import Callable, Iterator, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any, Protocol

from PIL import Image, ImageDraw

from person_search.api.errors import ApiError
from person_search.storage.postgres.models import CameraStatus
from person_search.workers.contracts import SampledFrame
from person_search.workers.errors import AIErrorCode, AIWorkerError
from person_search.workers.sampling import FrameSampler

DIAGNOSTIC_TEXT = "A person walking."
TIMEOUT_CODE = "diagnostic_timeout"
CONFIG_INVALID_CODE = "ai_config_invalid"


class Outcome(StrEnum):
    SUCCESS = "SUCCESS"
    INCONCLUSIVE = "INCONCLUSIVE"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"


@dataclass(frozen=True, slots=True)
class Step:
    component: str
    label: str
    outcome: Outcome
    message: str | None = None
    duration_ms: int | None = None
    code: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "component": self.component,
            "label": self.label,
            "outcome": self.outcome.value,
            "message": self.message,
            "duration_ms": self.duration_ms,
            "code": self.code,
        }


class Timer:
    def __enter__(self) -> Timer:
        self.start = time.perf_counter()
        self.ms = 0
        return self

    def __exit__(self, *args: object) -> None:
        self.ms = round((time.perf_counter() - self.start) * 1000)


def check_embedding(values: Sequence[float], dimension: int) -> str | None:
    if len(values) != dimension:
        return f"Embedding có {len(values)} chiều, cấu hình yêu cầu {dimension}."
    if not all(math.isfinite(value) for value in values):
        return "Embedding chứa giá trị không hợp lệ."
    if not math.isclose(math.sqrt(sum(v * v for v in values)), 1.0, abs_tol=1e-3):
        return "Embedding chưa được chuẩn hóa L2."
    return None


def error_code(error: BaseException) -> str:
    if isinstance(error, AIWorkerError):
        return error.code.value
    if isinstance(error, ApiError):
        return error.code
    return "diagnostic_failed"


def search_fixture_image() -> bytes:
    image = Image.new("RGB", (128, 256), (96, 110, 124))
    draw = ImageDraw.Draw(image)
    draw.ellipse((44, 12, 84, 52), fill=(210, 170, 140))
    draw.rectangle((36, 56, 92, 150), fill=(170, 30, 40))
    draw.rectangle((40, 150, 88, 240), fill=(30, 40, 90))
    output = io.BytesIO()
    try:
        image.save(output, format="PNG")
        return output.getvalue()
    finally:
        image.close()


@dataclass(frozen=True, slots=True)
class DiagnosticSettings:
    frame_stride: int = 5
    sample_frames: int = 6
    max_source_frames: int = 90
    deadline_seconds: float = 180.0
    rtsp_connect_timeout: float = 8.0
    rtsp_read_timeout: float = 8.0

    def __post_init__(self) -> None:
        for name in ("frame_stride", "sample_frames", "max_source_frames"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int) or value < 1:
                raise ValueError(f"{name} must be a positive integer.")
        if self.max_source_frames < self.sample_frames:
            raise ValueError("max_source_frames must cover sample_frames.")
        for name in ("deadline_seconds", "rtsp_connect_timeout", "rtsp_read_timeout"):
            value = getattr(self, name)
            if (
                isinstance(value, bool)
                or not isinstance(value, int | float)
                or not math.isfinite(value)
                or value <= 0
            ):
                raise ValueError(f"{name} must be a positive finite number.")

    @classmethod
    def from_environment(cls) -> DiagnosticSettings:
        return cls(
            deadline_seconds=float(os.getenv("PERSON_SEARCH_DIAGNOSTIC_TIMEOUT_SECONDS") or 180),
        )


class DiagnosticBusyError(RuntimeError):
    pass


class DiagnosticTimeout(RuntimeError):
    pass


class ComponentFactory(Protocol):
    def detector(self, selection: Any) -> Any: ...

    def tracker(self, selection: Any) -> Any: ...

    def image_encoder(self, selection: Any) -> Any: ...

    def query_gateway(self, selection: Any) -> Any: ...


SourceOpener = Callable[[Any, Callable[[], bool]], Any]


def camera_source_opener(
    runtime: Any,
    settings: DiagnosticSettings,
    *,
    sample_video: Path | None = None,
    rtsp_factory: Callable[..., Any] | None = None,
    file_factory: Callable[..., Any] | None = None,
) -> SourceOpener:
    def open_source(camera: Any, cancelled: Callable[[], bool]) -> Any:
        if camera.rtsp_url:
            if rtsp_factory is None:
                from person_search.workers.sources import RtspFrameSource

                factory = RtspFrameSource
            else:
                factory = rtsp_factory
            source = factory(
                encrypted_secret=camera.rtsp_credentials,
                access_resolver=runtime.connection_url,
                cancelled=cancelled,
                connect_timeout=settings.rtsp_connect_timeout,
                read_timeout=settings.rtsp_read_timeout,
                max_reconnects=0,
            )
            return source.open(camera.rtsp_url, camera_id=camera.id)
        if sample_video is not None:
            if file_factory is None:
                from person_search.workers.sources import FileFrameSource

                factory = FileFrameSource
            else:
                factory = file_factory
            return factory(cancelled=cancelled).open(sample_video, camera_id=camera.id)
        return None

    return open_source


def pipeline_labels(config: Any | None) -> list[tuple[str, str]]:
    if config is None:
        return [
            ("DETECTOR", "Detector"),
            ("TRACKER", "Tracker"),
            ("IMAGE_ENCODER", "Image Encoder"),
        ]
    return [
        ("DETECTOR", f"Detector · {config.detector_name} {config.detector_version}"),
        ("TRACKER", f"Tracker · {config.tracker_name} {config.tracker_version}"),
        ("IMAGE_ENCODER", f"Image Encoder · {config.encoder_name} {config.encoder_version}"),
    ]


def _close_quietly(component: Any) -> None:
    try:
        component.close()
    except Exception:
        pass


class ProductionDiagnostics:
    def __init__(
        self,
        registry: Any,
        components: ComponentFactory,
        source_opener: SourceOpener,
        *,
        settings: DiagnosticSettings | None = None,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.registry = registry
        self.components = components
        self.source_opener = source_opener
        self.settings = settings or DiagnosticSettings()
        self.clock = clock
        self._lock = threading.Lock()

    @contextmanager
    def _exclusive(self) -> Iterator[None]:
        if not self._lock.acquire(blocking=False):
            raise DiagnosticBusyError
        try:
            yield
        finally:
            self._lock.release()

    def _deadline(self) -> Callable[[], bool]:
        limit = self.clock() + self.settings.deadline_seconds
        return lambda: self.clock() > limit

    def camera_pipeline(self, camera: Any, config: Any | None) -> list[Step]:
        with self._exclusive():
            return _CameraPipelineRun(self, camera, config).run()

    def search_components(self, config: Any) -> list[Step]:
        with self._exclusive():
            return self._search_components(config)

    def _search_components(self, config: Any) -> list[Step]:
        name = f"{config.encoder_name} {config.encoder_version}"
        checks = (
            ("IMAGE_ENCODER", f"Image Encoder · {name}", "image", search_fixture_image()),
            ("TEXT_ENCODER", f"Text Encoder · {name}", "text", DIAGNOSTIC_TEXT),
        )
        try:
            selection = self.registry.resolve_config(config)
        except Exception:
            return [
                Step(
                    component,
                    label,
                    Outcome.FAILED,
                    "Cấu hình encoder không khớp registry production.",
                    code=CONFIG_INVALID_CODE,
                )
                for component, label, _, _ in checks
            ]
        expired = self._deadline()
        steps: list[Step] = []
        gateway = None
        try:
            for component, label, mode, payload in checks:
                if expired():
                    steps.append(
                        Step(
                            component,
                            label,
                            Outcome.FAILED,
                            "Quá thời gian kiểm tra.",
                            code=TIMEOUT_CODE,
                        )
                    )
                    continue
                with Timer() as timer:
                    try:
                        if gateway is None:
                            gateway = self.components.query_gateway(selection)
                            gateway.open()
                        call = gateway.image if mode == "image" else gateway.text
                        embedding = call(
                            payload,
                            version=config.encoder_version,
                            dimension=config.encoder_dimension,
                        )
                        problem, code = check_embedding(embedding, config.encoder_dimension), None
                        if problem:
                            code = (
                                AIErrorCode.IMAGE_ENCODER_OUTPUT_INVALID.value
                                if mode == "image"
                                else AIErrorCode.TEXT_ENCODER_OUTPUT_INVALID.value
                            )
                    except Exception as error:
                        problem = (
                            "Image Encoder không tải hoặc không thực thi được."
                            if mode == "image"
                            else "Text Encoder không tải hoặc không thực thi được."
                        )
                        code = error_code(error)
                        if gateway is not None:
                            _close_quietly(gateway)
                            gateway = None
                if expired() and not problem:
                    problem, code = "Quá thời gian kiểm tra.", TIMEOUT_CODE
                steps.append(
                    Step(
                        component,
                        label,
                        Outcome.FAILED if problem else Outcome.SUCCESS,
                        problem or f"Embedding {config.encoder_dimension} chiều.",
                        timer.ms,
                        code,
                    )
                )
        finally:
            if gateway is not None:
                _close_quietly(gateway)
        return steps


class _CameraPipelineRun:
    def __init__(self, owner: ProductionDiagnostics, camera: Any, config: Any | None) -> None:
        self.owner = owner
        self.camera = camera
        self.config = config
        self.labels = pipeline_labels(config)
        self.steps: list[Step] = []
        self.opened: list[Any] = []
        self.frames: list[SampledFrame] = []
        self.expired = owner._deadline()

    def skip_rest(self, reason: str, start: int) -> list[Step]:
        return self.steps + [
            Step(component, label, Outcome.SKIPPED, reason)
            for component, label in self.labels[start:]
        ]

    def fail(self, index: int, message: str, code: str | None, ms: int | None = None) -> None:
        component, label = self.labels[index]
        self.steps.append(Step(component, label, Outcome.FAILED, message, ms, code))

    def check_deadline(self) -> None:
        if self.expired():
            raise DiagnosticTimeout

    def open_component(self, build: Callable[[Any], Any], selection: Any) -> Any:
        component = build(selection)
        self.opened.append(component)
        component.open()
        return component

    def run(self) -> list[Step]:
        try:
            return self._run()
        finally:
            for component in reversed(self.opened):
                _close_quietly(component)
            for frame in self.frames:
                frame.source.image.close()

    def _run(self) -> list[Step]:
        camera = self.camera
        if camera.status is not CameraStatus.ACTIVE:
            self.steps.append(
                Step("FRAME_SOURCE", "Nguồn khung hình", Outcome.FAILED, "Camera không hoạt động.")
            )
            return self.skip_rest("Bỏ qua vì nguồn khung hình lỗi.", 0)
        if not camera.ai_enabled:
            self.steps.append(
                Step(
                    "FRAME_SOURCE",
                    "Nguồn khung hình",
                    Outcome.FAILED,
                    "Camera chưa bật xử lý AI.",
                )
            )
            return self.skip_rest("Bỏ qua vì camera chưa bật xử lý AI.", 0)
        if not self._read_frames():
            return self.skip_rest("Bỏ qua vì không có khung hình thật để kiểm tra.", 0)
        if self.config is None:
            self.fail(0, "Chưa có cấu hình AI đang áp dụng.", CONFIG_INVALID_CODE)
            return self.skip_rest("Bỏ qua vì chưa có cấu hình AI.", 1)
        try:
            selection = self.owner.registry.resolve_config(self.config)
        except Exception:
            self.fail(0, "Cấu hình AI không khớp registry production.", CONFIG_INVALID_CODE)
            return self.skip_rest("Bỏ qua vì không nạp được mô hình.", 1)
        detections = self._detect(selection)
        if detections is None:
            return self.skip_rest("Bỏ qua vì Detector lỗi.", 1)
        if not any(detections):
            return self.skip_rest("Chưa có người trong khung hình để kiểm tra tiếp.", 1)
        updates = self._track(selection, detections)
        if updates is None:
            return self.skip_rest("Bỏ qua vì Tracker lỗi.", 2)
        self._encode(selection, detections, updates)
        return self.steps

    def _read_frames(self) -> bool:
        settings = self.owner.settings
        label = "Nhận khung hình RTSP" if self.camera.rtsp_url else "Video mẫu chẩn đoán"
        sampler = FrameSampler.for_benchmark(settings.frame_stride)
        message = code = None
        missing = False
        with Timer() as timer:
            try:
                source = self.owner.source_opener(self.camera, self.expired)
                if source is None:
                    missing = True
                else:
                    with source:
                        for read, frame in enumerate(source, start=1):
                            sampled = sampler.sample(frame)
                            if sampled is None:
                                frame.image.close()
                            else:
                                self.frames.append(sampled)
                            if (
                                len(self.frames) >= settings.sample_frames
                                or read >= settings.max_source_frames
                            ):
                                break
                            self.check_deadline()
            except DiagnosticTimeout:
                message, code = "Quá thời gian nhận khung hình.", TIMEOUT_CODE
            except ApiError as error:
                message, code = error.message, error.code
            except AIWorkerError as error:
                if error.code is AIErrorCode.CANCELLED:
                    message, code = "Quá thời gian nhận khung hình.", TIMEOUT_CODE
                else:
                    message, code = "Không nhận được khung hình từ nguồn.", error.code.value
            except Exception as error:
                message, code = "Không nhận được khung hình từ nguồn.", error_code(error)
        if missing:
            self.steps.append(
                Step(
                    "FRAME_SOURCE",
                    "Nguồn khung hình",
                    Outcome.INCONCLUSIVE,
                    "Camera không cấu hình RTSP và máy chủ chưa có video mẫu chẩn đoán; "
                    "không dùng khung hình tổng hợp.",
                    code="diagnostic_source_missing",
                )
            )
            return False
        if message is None and not self.frames:
            message, code = "Nguồn không trả về khung hình nào.", "source_empty"
        if message is not None:
            self.steps.append(Step("FRAME_SOURCE", label, Outcome.FAILED, message, timer.ms, code))
            return False
        first = self.frames[0]
        self.steps.append(
            Step(
                "FRAME_SOURCE",
                label,
                Outcome.SUCCESS,
                f"Nhận {len(self.frames)} khung hình {first.width}×{first.height}.",
                timer.ms,
            )
        )
        return True

    def _detect(self, selection: Any) -> list[tuple[Any, ...]] | None:
        results: list[tuple[Any, ...]] = []
        failure = None
        with Timer() as timer:
            try:
                detector = self.open_component(self.owner.components.detector, selection)
                for frame in self.frames:
                    self.check_deadline()
                    results.append(tuple(detector.detect(frame)))
                self.check_deadline()
            except DiagnosticTimeout:
                failure = ("Quá thời gian kiểm tra Detector.", TIMEOUT_CODE)
            except Exception as error:
                failure = ("Detector không tải hoặc không thực thi được.", error_code(error))
        if failure is not None:
            self.fail(0, *failure, timer.ms)
            return None
        total = sum(len(item) for item in results)
        component, label = self.labels[0]
        if not total:
            self.steps.append(
                Step(
                    component,
                    label,
                    Outcome.INCONCLUSIVE,
                    f"Không có người trong {len(self.frames)} khung hình kiểm tra.",
                    timer.ms,
                    "no_person_detected",
                )
            )
        else:
            self.steps.append(
                Step(
                    component,
                    label,
                    Outcome.SUCCESS,
                    f"{total} vùng người trên {len(self.frames)} khung hình.",
                    timer.ms,
                )
            )
        return results

    def _track(self, selection: Any, detections: list[tuple[Any, ...]]) -> list[Any] | None:
        updates: list[Any] = []
        failure = None
        with Timer() as timer:
            try:
                tracker = self.open_component(self.owner.components.tracker, selection)
                for frame, frame_detections in zip(self.frames, detections, strict=True):
                    self.check_deadline()
                    updates.extend(tracker.update(frame, frame_detections))
                updates.extend(tracker.flush())
                self.check_deadline()
            except DiagnosticTimeout:
                failure = ("Quá thời gian kiểm tra Tracker.", TIMEOUT_CODE)
            except Exception as error:
                failure = (
                    "Tracker không khởi tạo hoặc không xử lý được detection.",
                    error_code(error),
                )
        if failure is not None:
            self.fail(1, *failure, timer.ms)
            return None
        component, label = self.labels[1]
        track_ids = {update.local_track_id for update in updates}
        if track_ids:
            self.steps.append(
                Step(component, label, Outcome.SUCCESS, f"{len(track_ids)} track.", timer.ms)
            )
        else:
            self.steps.append(
                Step(
                    component,
                    label,
                    Outcome.INCONCLUSIVE,
                    f"Tracker chạy nhưng chưa xác nhận track trong {len(self.frames)} khung hình.",
                    timer.ms,
                    "no_confirmed_track",
                )
            )
        return updates

    def _crop_target(self, detections: list[tuple[Any, ...]], updates: list[Any]):
        by_index = {frame.source_frame_index: frame for frame in self.frames}
        for update in updates:
            frame = by_index.get(update.source_frame_index)
            if frame is not None:
                return frame, update.bbox
        best = max(
            (
                (detection.confidence, index, detection.bbox)
                for index, items in enumerate(detections)
                for detection in items
            ),
            key=lambda item: (item[0], -item[1]),
        )
        return self.frames[best[1]], best[2]

    def _encode(
        self, selection: Any, detections: list[tuple[Any, ...]], updates: list[Any]
    ) -> None:
        component, label = self.labels[2]
        frame, bbox = self._crop_target(detections, updates)
        crop = None
        with Timer() as timer:
            try:
                encoder = self.open_component(self.owner.components.image_encoder, selection)
                self.check_deadline()
                crop = frame.source.image.crop(
                    (bbox.x, bbox.y, bbox.x + bbox.width, bbox.y + bbox.height)
                )
                embedding = encoder.encode(crop)
                values = getattr(embedding, "values", embedding)
                problem = check_embedding(values, self.config.encoder_dimension)
                code = AIErrorCode.IMAGE_ENCODER_OUTPUT_INVALID.value if problem else None
                self.check_deadline()
            except DiagnosticTimeout:
                problem, code = "Quá thời gian kiểm tra Image Encoder.", TIMEOUT_CODE
            except Exception as error:
                problem = "Image Encoder không tải hoặc không thực thi được."
                code = error_code(error)
            finally:
                if crop is not None:
                    crop.close()
        self.steps.append(
            Step(
                component,
                label,
                Outcome.FAILED if problem else Outcome.SUCCESS,
                problem or f"Embedding {self.config.encoder_dimension} chiều.",
                timer.ms,
                code,
            )
        )
