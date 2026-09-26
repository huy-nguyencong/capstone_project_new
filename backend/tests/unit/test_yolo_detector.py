from __future__ import annotations

import hashlib
import uuid
from pathlib import Path

import pytest
from PIL import Image

from person_search.ai.detectors import (
    DetectorSettings,
    RawDetection,
    UltralyticsProcessBackend,
    YoloPersonDetector,
    build_yolo_detector,
    load_detector_settings,
)
from person_search.ai.registry import (
    ArtifactReference,
    DetectorEntry,
    DeviceKind,
    Provenance,
)
from person_search.workers.contracts import ModelLineage, SampledFrame, SourceFrame
from person_search.workers.errors import AIErrorCode, AIWorkerError

pytestmark = pytest.mark.unit


class FakeBackend:
    def __init__(self, rows=(), *, open_error=None, predict_error=None):
        self.rows = rows
        self.open_error = open_error
        self.predict_error = predict_error
        self.open_calls = 0
        self.predict_calls = []
        self.close_calls = 0

    def open(self):
        self.open_calls += 1
        if self.open_error:
            raise self.open_error

    def predict(self, image, *, timeout_seconds):
        self.predict_calls.append((image.size, timeout_seconds))
        if self.predict_error:
            raise self.predict_error
        return self.rows

    def close(self):
        self.close_calls += 1


def _sample(width=100, height=50) -> SampledFrame:
    source = SourceFrame(
        camera_id=uuid.uuid4(),
        source_frame_index=20,
        source_timestamp_ms=817,
        image=Image.new("RGB", (width, height), "navy"),
        width=width,
        height=height,
    )
    return SampledFrame(source, sampling_interval=10, sample_sequence=2)


def _detector(backend, **settings) -> YoloPersonDetector:
    return YoloPersonDetector(
        backend,
        lineage=ModelLineage("approved_yolo", "1.0.0", "a" * 64),
        person_class_id=0,
        settings=DetectorSettings(**settings),
    )


def test_person_filter_confidence_and_bbox_mapping_use_original_frame_pixels() -> None:
    backend = FakeBackend(
        [
            RawDetection(-2.2, 2.8, 101.1, 55, 0, 0.9),
            RawDetection(10, 10, 30, 30, 2, 0.99),
            RawDetection(10, 10, 30, 30, 0, 0.1),
            RawDetection(120, 10, 130, 20, 0, 0.8),
        ]
    )
    detector = _detector(backend, confidence_threshold=0.25)
    detector.open()

    detections = detector.detect(_sample())

    assert len(detections) == 1
    detection = detections[0]
    assert (
        detection.bbox.x,
        detection.bbox.y,
        detection.bbox.width,
        detection.bbox.height,
        detection.bbox.frame_width,
        detection.bbox.frame_height,
    ) == (0, 2, 100, 48, 100, 50)
    assert detection.class_name == "person" and detection.confidence == 0.9
    assert detection.detector.registry_id == "approved_yolo"
    assert backend.predict_calls == [((100, 50), 120.0)]


def test_detector_records_backend_latency_without_retaining_frame_payload() -> None:
    readings = iter([10.0, 10.025])
    backend = FakeBackend([])
    detector = YoloPersonDetector(
        backend,
        lineage=ModelLineage("approved_yolo", "1.0.0", "a" * 64),
        person_class_id=0,
        settings=DetectorSettings(),
        clock=lambda: next(readings),
    )
    detector.open()

    assert detector.detect(_sample()) == ()
    assert detector.metrics.inference_count == 1
    assert detector.metrics.last_latency_ms == pytest.approx(25)


@pytest.mark.parametrize("size", [(32, 96), (1920, 1080)])
def test_empty_and_different_frame_sizes_are_supported(size) -> None:
    backend = FakeBackend([])
    detector = _detector(backend)
    detector.open()

    assert detector.detect(_sample(*size)) == ()


@pytest.mark.parametrize(
    "rows",
    [
        [RawDetection(float("nan"), 0, 10, 10, 0, 0.9)],
        [RawDetection(0, 0, 10, 10, True, 0.9)],
        [RawDetection(0, 0, 10, 10, 0, 1.1)],
        [object()],
    ],
)
def test_invalid_model_output_fails_closed(rows) -> None:
    backend = FakeBackend(rows)
    detector = _detector(backend)
    detector.open()

    with pytest.raises(AIWorkerError) as caught:
        detector.detect(_sample())

    assert caught.value.code is AIErrorCode.DETECTOR_OUTPUT_INVALID
    assert backend.close_calls == 1


def test_excess_output_is_rejected_before_tracker_boundary() -> None:
    backend = FakeBackend([RawDetection(0, 0, 2, 2, 0, 0.9)] * 3)
    detector = _detector(backend, max_detections=2)
    detector.open()

    with pytest.raises(AIWorkerError) as caught:
        detector.detect(_sample())
    assert caught.value.code is AIErrorCode.DETECTOR_OUTPUT_INVALID


@pytest.mark.parametrize(
    ("error", "code"),
    [
        (TimeoutError("private timeout detail"), AIErrorCode.DETECTOR_TIMEOUT),
        (RuntimeError("private model path"), AIErrorCode.DETECTOR_INFERENCE_FAILED),
    ],
)
def test_timeout_and_inference_failure_are_sanitized_and_release_backend(error, code) -> None:
    backend = FakeBackend(predict_error=error)
    detector = _detector(backend, inference_timeout_seconds=0.1)
    detector.open()

    with pytest.raises(AIWorkerError) as caught:
        detector.detect(_sample())

    assert caught.value.code is code
    assert "private" not in str(caught.value)
    assert backend.close_calls == 1


def test_model_load_failure_and_close_are_fail_closed_and_idempotent() -> None:
    backend = FakeBackend(open_error=RuntimeError("missing optional package"))
    detector = _detector(backend)

    with pytest.raises(AIWorkerError) as caught:
        detector.open()
    detector.close()

    assert caught.value.code is AIErrorCode.DETECTOR_UNAVAILABLE
    assert backend.close_calls == 1


@pytest.mark.parametrize(
    "values",
    [
        {"confidence_threshold": -0.1},
        {"iou_threshold": float("inf")},
        {"inference_timeout_seconds": 0},
        {"max_detections": 1.5},
    ],
)
def test_detector_settings_reject_invalid_resource_limits(values) -> None:
    with pytest.raises(ValueError):
        DetectorSettings(**values)


def _entry(path: str, digest: str, *, available=True) -> DetectorEntry:
    return DetectorEntry(
        id="approved_yolo",
        display_name="Approved YOLO",
        version="1.0.0",
        description="Unit-test registry entry.",
        adapter_kind="ultralytics_yolo",
        artifact=ArtifactReference(path, digest),
        devices=(DeviceKind.CPU,),
        input_shape=(3, 640, 640),
        provenance=Provenance(
            "ultralytics",
            "1.0.0",
            "https://example.com/source",
            "https://example.com/weights",
            "approved-test-license",
            True,
            "Approved for unit testing.",
        ),
        available=available,
        unavailable_reasons=() if available else ("license_not_approved",),
        person_class_id=0,
        preprocessing_version="letterbox_rgb_v1",
    )


def test_factory_uses_registry_artifact_shape_device_and_lineage(tmp_path: Path) -> None:
    artifact = tmp_path / "model.pt"
    artifact.write_bytes(b"approved checkpoint fixture")
    digest = hashlib.sha256(artifact.read_bytes()).hexdigest()
    built = {}

    def backend_factory(path, **options):
        built.update(path=path, **options)
        return FakeBackend()

    detector = build_yolo_detector(
        _entry("model.pt", digest),
        artifact_root=tmp_path,
        backend_factory=backend_factory,
    )

    assert detector.lineage == ModelLineage("approved_yolo", "1.0.0", digest)
    assert built["path"] == artifact
    assert built["device"] == "cpu"
    assert built["image_size"] == (640, 640)
    assert built["person_class_id"] == 0

    artifact.write_bytes(b"changed")
    with pytest.raises(ValueError, match="checksum changed"):
        build_yolo_detector(_entry("model.pt", digest), artifact_root=tmp_path)


def test_factory_rejects_unapproved_registry_entry_before_importing_model(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="not available"):
        build_yolo_detector(_entry("missing.pt", "0" * 64, available=False), artifact_root=tmp_path)


def test_versioned_detector_settings_load_strictly(tmp_path: Path) -> None:
    configured = Path(__file__).parents[2] / "config" / "ultralytics_yolo_detector.json"
    assert load_detector_settings(configured) == DetectorSettings()

    invalid = tmp_path / "invalid.json"
    invalid.write_text('{"schema_version":"ultralytics-yolo-detector/v1"}', encoding="utf-8")
    with pytest.raises(ValueError, match="fields"):
        load_detector_settings(invalid)


class FakeConnection:
    def __init__(self, *, ready=False):
        self.ready = ready
        self.sent = []
        self.closed = False

    def poll(self, timeout):
        del timeout
        return self.ready

    def recv(self):
        return ("ready", None)

    def send(self, value):
        self.sent.append(value)

    def close(self):
        self.closed = True


class FakeProcess:
    def __init__(self):
        self.started = False
        self.alive = True
        self.terminated = False
        self.closed = False

    def start(self):
        self.started = True

    def is_alive(self):
        return self.alive

    def join(self, timeout=None):
        del timeout

    def terminate(self):
        self.terminated = True
        self.alive = False

    def kill(self):
        self.alive = False

    def close(self):
        self.closed = True


class FakeContext:
    def __init__(self, parent, child, process):
        self.parent, self.child, self.process = parent, child, process

    def Pipe(self):
        return self.parent, self.child

    def Process(self, **kwargs):
        assert kwargs["daemon"] is True
        return self.process


def test_process_backend_kills_model_process_when_load_times_out(tmp_path: Path) -> None:
    parent, child, process = FakeConnection(), FakeConnection(), FakeProcess()
    context = FakeContext(parent, child, process)
    backend = UltralyticsProcessBackend(
        tmp_path / "model.pt",
        device="cpu",
        image_size=(640, 640),
        person_class_id=0,
        settings=DetectorSettings(load_timeout_seconds=0.01),
        context_factory=lambda method: context,
    )

    with pytest.raises(TimeoutError, match="load timed out"):
        backend.open()

    assert process.started and process.terminated and process.closed
    assert parent.closed and child.closed
