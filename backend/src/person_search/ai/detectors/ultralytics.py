"""Process-isolated Ultralytics YOLO person detector."""

from __future__ import annotations

import json
import math
import multiprocessing
import os
import tempfile
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from hashlib import sha256
from multiprocessing.connection import Connection
from pathlib import Path, PurePosixPath
from typing import Any, Protocol

from PIL import Image

from person_search.ai.registry import DetectorEntry
from person_search.storage.contracts import BoundingBoxPixels
from person_search.workers.contracts import Detection, ModelLineage, SampledFrame
from person_search.workers.errors import AIErrorCode, AIWorkerError


@dataclass(frozen=True, slots=True)
class DetectorSettings:
    confidence_threshold: float = 0.1
    iou_threshold: float = 0.7
    inference_timeout_seconds: float = 120.0
    load_timeout_seconds: float = 120.0
    max_detections: int = 300

    def __post_init__(self) -> None:
        for name in ("confidence_threshold", "iou_threshold"):
            value = getattr(self, name)
            if not isinstance(value, (int, float)) or isinstance(value, bool):
                raise ValueError(f"{name} must be numeric.")
            if not math.isfinite(value) or not 0 <= value <= 1:
                raise ValueError(f"{name} must be between zero and one.")
        if any(
            not isinstance(value, (int, float))
            or isinstance(value, bool)
            or not math.isfinite(value)
            or value <= 0
            for value in (self.inference_timeout_seconds, self.load_timeout_seconds)
        ):
            raise ValueError("Detector timeouts must be positive.")
        if (
            isinstance(self.max_detections, bool)
            or not isinstance(self.max_detections, int)
            or self.max_detections < 1
        ):
            raise ValueError("max_detections must be a positive integer.")


def load_detector_settings(path: str | Path) -> DetectorSettings:
    """Load the deployment-owned YOLO thresholds without accepting unknown fields."""

    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError("Detector settings file is unreadable.") from exc
    expected = {
        "schema_version",
        "confidence_threshold",
        "iou_threshold",
        "inference_timeout_seconds",
        "load_timeout_seconds",
        "max_detections",
    }
    if not isinstance(payload, dict) or set(payload) != expected:
        raise ValueError("Detector settings fields do not match the schema.")
    if payload.pop("schema_version") != "ultralytics-yolo-detector/v1":
        raise ValueError("Detector settings schema_version is unsupported.")
    return DetectorSettings(**payload)


@dataclass(frozen=True, slots=True)
class RawDetection:
    x1: float
    y1: float
    x2: float
    y2: float
    class_id: int
    confidence: float


@dataclass(frozen=True, slots=True)
class DetectorMetrics:
    inference_count: int
    last_latency_ms: float | None


class DetectorBackend(Protocol):
    def open(self) -> None: ...

    def predict(self, image: Image.Image, *, timeout_seconds: float) -> Sequence[RawDetection]: ...

    def close(self) -> None: ...


def _ultralytics_child(
    connection: Connection,
    artifact_path: str,
    device: str,
    image_size: tuple[int, int],
    confidence_threshold: float,
    iou_threshold: float,
    max_detections: int,
    person_class_id: int,
) -> None:
    """Own all model/tensor state so a timed-out inference can be terminated safely."""

    try:
        image_open = Image.open
        config_key = "YOLO_CONFIG_DIR"
        previous_config_dir = os.environ.get(config_key)
        if previous_config_dir is None:
            config_dir = Path(tempfile.gettempdir()) / "person-search-ultralytics"
            config_dir.mkdir(parents=True, exist_ok=True)
            os.environ[config_key] = str(config_dir)
        from ultralytics import YOLO

        model = YOLO(artifact_path)
        connection.send(("ready", None))
    except BaseException:
        connection.send(("load_error", None))
        connection.close()
        return
    finally:
        Image.open = image_open
        if previous_config_dir is None:
            os.environ.pop(config_key, None)
    try:
        while True:
            command, payload = connection.recv()
            if command == "close":
                return
            if command != "predict":
                connection.send(("inference_error", None))
                continue
            results = None
            try:
                results = model.predict(
                    source=payload,
                    imgsz=image_size,
                    conf=confidence_threshold,
                    iou=iou_threshold,
                    max_det=max_detections,
                    classes=[person_class_id],
                    device=device,
                    verbose=False,
                )
                rows = []
                for result in results:
                    boxes = result.boxes
                    coordinates = boxes.xyxy.detach().cpu().tolist()
                    classes = boxes.cls.detach().cpu().tolist()
                    confidences = boxes.conf.detach().cpu().tolist()
                    rows.extend(
                        (box[0], box[1], box[2], box[3], int(class_id), confidence)
                        for box, class_id, confidence in zip(
                            coordinates, classes, confidences, strict=True
                        )
                    )
                connection.send(("ok", rows))
            except BaseException:
                connection.send(("inference_error", None))
            finally:
                del results
    except (EOFError, BrokenPipeError):
        return
    finally:
        connection.close()


class UltralyticsProcessBackend:
    """Run the optional model package in a killable child process."""

    def __init__(
        self,
        artifact_path: Path,
        *,
        device: str,
        image_size: tuple[int, int],
        person_class_id: int,
        settings: DetectorSettings,
        context_factory: Callable[[str], Any] = multiprocessing.get_context,
    ) -> None:
        self.artifact_path = Path(artifact_path)
        self.device = device
        self.image_size = image_size
        self.person_class_id = person_class_id
        self.settings = settings
        self._context_factory = context_factory
        self._connection: Connection | None = None
        self._process: Any | None = None

    def open(self) -> None:
        if self._process is not None:
            raise RuntimeError("Detector backend is already open.")
        context = self._context_factory("spawn")
        parent, child = context.Pipe()
        process = context.Process(
            target=_ultralytics_child,
            args=(
                child,
                str(self.artifact_path),
                self.device,
                self.image_size,
                self.settings.confidence_threshold,
                self.settings.iou_threshold,
                self.settings.max_detections,
                self.person_class_id,
            ),
            daemon=True,
        )
        process.start()
        child.close()
        self._connection, self._process = parent, process
        if not parent.poll(self.settings.load_timeout_seconds):
            self.close()
            raise TimeoutError("Detector model load timed out.")
        status, _ = parent.recv()
        if status != "ready":
            self.close()
            raise RuntimeError("Detector model could not be loaded.")

    def predict(self, image: Image.Image, *, timeout_seconds: float) -> Sequence[RawDetection]:
        if self._connection is None or self._process is None or not self._process.is_alive():
            raise RuntimeError("Detector backend is unavailable.")
        self._connection.send(("predict", image.copy()))
        if not self._connection.poll(timeout_seconds):
            self.close()
            raise TimeoutError("Detector inference timed out.")
        status, payload = self._connection.recv()
        if status != "ok" or not isinstance(payload, list):
            raise RuntimeError("Detector inference failed.")
        return tuple(RawDetection(*row) for row in payload)

    def close(self) -> None:
        connection, self._connection = self._connection, None
        process, self._process = self._process, None
        if connection is not None:
            try:
                if process is not None and process.is_alive():
                    connection.send(("close", None))
            except (BrokenPipeError, EOFError, OSError):
                pass
            connection.close()
        if process is not None:
            process.join(timeout=2)
            if process.is_alive():
                process.terminate()
                process.join(timeout=5)
            if process.is_alive():
                process.kill()
                process.join()
            process.close()


class YoloPersonDetector:
    """Validate model output and expose only person detections in source pixel space."""

    def __init__(
        self,
        backend: DetectorBackend,
        *,
        lineage: ModelLineage,
        person_class_id: int,
        settings: DetectorSettings,
        clock: Callable[[], float] = time.perf_counter,
    ) -> None:
        self._backend = backend
        self.lineage = lineage
        self.person_class_id = person_class_id
        self.settings = settings
        self._clock = clock
        self._opened = False
        self._closed = False
        self._inference_count = 0
        self._last_latency_ms: float | None = None

    @property
    def metrics(self) -> DetectorMetrics:
        return DetectorMetrics(self._inference_count, self._last_latency_ms)

    def open(self) -> None:
        if self._opened or self._closed:
            raise RuntimeError("Detector instances are one-shot.")
        try:
            self._backend.open()
        except Exception as exc:
            self.close()
            raise AIWorkerError(AIErrorCode.DETECTOR_UNAVAILABLE, cause=exc) from exc
        self._opened = True

    def detect(self, frame: SampledFrame) -> Sequence[Detection]:
        if not self._opened or self._closed:
            raise RuntimeError("Detector must be open before inference.")
        if not isinstance(frame, SampledFrame):
            raise TypeError("Detector accepts SampledFrame values only.")
        started = self._clock()
        try:
            raw = tuple(
                self._backend.predict(
                    frame.image,
                    timeout_seconds=self.settings.inference_timeout_seconds,
                )
            )
        except TimeoutError as exc:
            self.close()
            raise AIWorkerError(AIErrorCode.DETECTOR_TIMEOUT, cause=exc) from exc
        except Exception as exc:
            self.close()
            raise AIWorkerError(AIErrorCode.DETECTOR_INFERENCE_FAILED, cause=exc) from exc
        finally:
            self._inference_count += 1
            self._last_latency_ms = max(0.0, (self._clock() - started) * 1000)
        try:
            return self._normalize(raw, frame)
        except (TypeError, ValueError) as exc:
            self.close()
            raise AIWorkerError(AIErrorCode.DETECTOR_OUTPUT_INVALID, cause=exc) from exc
        finally:
            del raw

    def _normalize(self, raw: Sequence[RawDetection], frame: SampledFrame) -> tuple[Detection, ...]:
        if len(raw) > self.settings.max_detections:
            raise ValueError("Detector exceeded max_detections.")
        detections = []
        for item in raw:
            if not isinstance(item, RawDetection):
                raise TypeError("Detector backend returned an invalid row.")
            values = (item.x1, item.y1, item.x2, item.y2, item.confidence)
            if not all(
                isinstance(value, (int, float))
                and not isinstance(value, bool)
                and math.isfinite(value)
                for value in values
            ):
                raise ValueError("Detector output must contain finite numbers.")
            if isinstance(item.class_id, bool) or not isinstance(item.class_id, int):
                raise ValueError("Detector class ID must be an integer.")
            if not 0 <= item.confidence <= 1:
                raise ValueError("Detector confidence must be between zero and one.")
            if item.class_id != self.person_class_id:
                continue
            if item.confidence < self.settings.confidence_threshold:
                continue
            x1 = max(0, min(frame.width, math.floor(item.x1)))
            y1 = max(0, min(frame.height, math.floor(item.y1)))
            x2 = max(0, min(frame.width, math.ceil(item.x2)))
            y2 = max(0, min(frame.height, math.ceil(item.y2)))
            if x2 <= x1 or y2 <= y1:
                continue
            detections.append(
                Detection(
                    bbox=BoundingBoxPixels(
                        x1,
                        y1,
                        x2 - x1,
                        y2 - y1,
                        frame.width,
                        frame.height,
                    ),
                    class_id=self.person_class_id,
                    class_name="person",
                    confidence=float(item.confidence),
                    detector=self.lineage,
                )
            )
        return tuple(detections)

    def close(self) -> None:
        if self._closed:
            return
        try:
            self._backend.close()
        finally:
            self._closed = True


def build_yolo_detector(
    entry: DetectorEntry,
    *,
    artifact_root: str | Path,
    device: str = "cpu",
    settings: DetectorSettings | None = None,
    backend_factory: Callable[..., DetectorBackend] = UltralyticsProcessBackend,
) -> YoloPersonDetector:
    """Build only a registry-approved Ultralytics detector with a verified local artifact."""

    if not isinstance(entry, DetectorEntry) or entry.adapter_kind != "ultralytics_yolo":
        raise ValueError("Detector entry is not an Ultralytics YOLO adapter.")
    if not entry.available:
        raise ValueError("Detector entry is not available for production.")
    if device not in {item.value for item in entry.devices}:
        raise ValueError("Requested detector device is not allowlisted.")
    if len(entry.input_shape) != 3 or entry.input_shape[0] != 3:
        raise ValueError("Detector registry input_shape must be CHW RGB.")
    if entry.preprocessing_version != "letterbox_rgb_v1":
        raise ValueError("Detector preprocessing version is not supported.")
    root = Path(artifact_root).resolve()
    artifact = (root / Path(*PurePosixPath(entry.artifact.relative_path).parts)).resolve()
    if not artifact.is_relative_to(root) or not artifact.is_file():
        raise ValueError("Detector artifact is unavailable.")
    digest = sha256()
    with artifact.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)
    if digest.hexdigest() != entry.artifact.sha256:
        raise ValueError("Detector artifact checksum changed.")
    selected_settings = settings or DetectorSettings()
    backend = backend_factory(
        artifact,
        device=device,
        image_size=(entry.input_shape[1], entry.input_shape[2]),
        person_class_id=entry.person_class_id,
        settings=selected_settings,
    )
    return YoloPersonDetector(
        backend,
        lineage=ModelLineage(entry.id, entry.version, entry.artifact.sha256),
        person_class_id=entry.person_class_id,
        settings=selected_settings,
    )
