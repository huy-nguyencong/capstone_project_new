from __future__ import annotations

import io
import math
import uuid
from pathlib import Path
from types import SimpleNamespace

import pytest
from PIL import Image

from person_search.api.errors import ApiError
from person_search.services.diagnostics import (
    DIAGNOSTIC_TEXT,
    DiagnosticBusyError,
    DiagnosticSettings,
    Outcome,
    ProductionDiagnostics,
    camera_source_opener,
    search_fixture_image,
)
from person_search.services.monitoring import MonitoringService, overall
from person_search.storage.contracts import BoundingBoxPixels
from person_search.storage.postgres.models import CameraStatus
from person_search.workers.contracts import (
    Detection,
    EmbeddingVector,
    ModelLineage,
    SourceFrame,
    TrackState,
    TrackUpdate,
)
from person_search.workers.errors import AIErrorCode, AIWorkerError

pytestmark = pytest.mark.unit

DIMENSION = 4
LINEAGE = ModelLineage("component", "1", "a" * 64)
CONFIG = SimpleNamespace(
    detector_name="yolo11n_coco",
    detector_version="1",
    tracker_name="bytetrack_v1",
    tracker_version="1",
    encoder_name="rasa_cuhk_pedes_v1",
    encoder_version="rasa_v1",
    encoder_dimension=DIMENSION,
)
UNIT = (1.0, 0.0, 0.0, 0.0)


def camera(**overrides):
    values = dict(
        id=uuid.uuid4(),
        status=CameraStatus.ACTIVE,
        ai_enabled=True,
        rtsp_url="rtsp://10.0.0.5/stream",
        rtsp_credentials="encrypted-token",
    )
    values.update(overrides)
    return SimpleNamespace(**values)


class Source:
    def __init__(self, camera_id, count=30, width=64, height=48):
        self.camera_id = camera_id
        self.count = count
        self.width = width
        self.height = height
        self.closed = False
        self.images = []

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.closed = True

    def __iter__(self):
        for index in range(self.count):
            image = Image.new("RGB", (self.width, self.height), (index, index, index))
            self.images.append(image)
            yield SourceFrame(self.camera_id, index, index * 40, image, self.width, self.height)


def detection(x=10, y=5, confidence=0.9):
    return Detection(
        BoundingBoxPixels(x, y, 20, 30, 64, 48), 0, "person", confidence, LINEAGE
    )


class Component:
    def __init__(self, log, name, *, open_error=None):
        self.log = log
        self.name = name
        self.open_error = open_error

    def open(self):
        self.log.append(("open", self.name))
        if self.open_error is not None:
            raise self.open_error

    def close(self):
        self.log.append(("close", self.name))


class Detector(Component):
    def __init__(self, log, *, per_frame=1, error=None, open_error=None, on_detect=None):
        super().__init__(log, "detector", open_error=open_error)
        self.per_frame = per_frame
        self.error = error
        self.on_detect = on_detect
        self.frames = []

    def detect(self, frame):
        if self.on_detect is not None:
            self.on_detect()
        if self.error is not None:
            raise self.error
        self.frames.append(frame)
        return tuple(detection(x=10 + i) for i in range(self.per_frame))


class Tracker(Component):
    def __init__(self, log, *, error=None, confirm=True):
        super().__init__(log, "tracker")
        self.error = error
        self.confirm = confirm
        self.sequences = []

    def update(self, frame, detections):
        if self.error is not None:
            raise self.error
        self.sequences.append(frame.sample_sequence)
        if not self.confirm or not detections:
            return ()
        return (
            TrackUpdate(
                "bt-1",
                frame.camera_id,
                detections[0].bbox,
                frame.source_frame_index,
                frame.source_timestamp_ms,
                TrackState.ACTIVE,
                LINEAGE,
            ),
        )

    def flush(self):
        return ()


class Encoder(Component):
    def __init__(self, log, *, values=UNIT, error=None, open_error=None):
        super().__init__(log, "encoder", open_error=open_error)
        self.values = values
        self.error = error
        self.crops = []

    def encode(self, crop):
        self.crops.append(crop)
        if self.error is not None:
            raise self.error
        return EmbeddingVector(self.values, DIMENSION, True, LINEAGE)


class Components:
    def __init__(self, *, detector=None, tracker=None, encoder=None, gateways=None):
        self.log = []
        self.detector_instance = detector or Detector(self.log)
        self.tracker_instance = tracker or Tracker(self.log)
        self.encoder_instance = encoder or Encoder(self.log)
        for item in (self.detector_instance, self.tracker_instance, self.encoder_instance):
            item.log = self.log
        self.gateways = list(gateways or [])
        self.built = []

    def detector(self, selection):
        self.built.append("detector")
        return self.detector_instance

    def tracker(self, selection):
        self.built.append("tracker")
        return self.tracker_instance

    def image_encoder(self, selection):
        self.built.append("encoder")
        return self.encoder_instance

    def query_gateway(self, selection):
        self.built.append("gateway")
        gateway = self.gateways.pop(0) if self.gateways else Gateway()
        return gateway


class Registry:
    def __init__(self, error=None):
        self.error = error
        self.configs = []

    def resolve_config(self, config):
        self.configs.append(config)
        if self.error is not None:
            raise self.error
        return SimpleNamespace(name="selection")


class Clock:
    def __init__(self):
        self.value = 0.0

    def __call__(self):
        return self.value


def diagnostics(components=None, *, opener=None, registry=None, clock=None, **settings):
    sources = []

    def default_opener(target, cancelled):
        source = Source(target.id)
        sources.append(source)
        return source

    subject = ProductionDiagnostics(
        registry or Registry(),
        components or Components(),
        opener or default_opener,
        settings=DiagnosticSettings(**settings),
        clock=clock or Clock(),
    )
    return subject, sources


def outcomes(steps):
    return [(step.component, step.outcome) for step in steps]


def test_real_frames_flow_through_every_production_component():
    components = Components()
    subject, sources = diagnostics(components, frame_stride=5, sample_frames=6)

    steps = subject.camera_pipeline(camera(), CONFIG)

    assert outcomes(steps) == [
        ("FRAME_SOURCE", Outcome.SUCCESS),
        ("DETECTOR", Outcome.SUCCESS),
        ("TRACKER", Outcome.SUCCESS),
        ("IMAGE_ENCODER", Outcome.SUCCESS),
    ]
    assert overall(steps) is Outcome.SUCCESS
    assert "6 khung hình 64×48" in steps[0].message
    assert [frame.source_frame_index for frame in components.detector_instance.frames] == [
        0,
        5,
        10,
        15,
        20,
        25,
    ]
    assert components.tracker_instance.sequences == [0, 1, 2, 3, 4, 5]
    assert components.log[-3:] == [
        ("close", "encoder"),
        ("close", "tracker"),
        ("close", "detector"),
    ]
    source = sources[0]
    assert source.closed
    assert all(image_closed(image) for image in source.images)
    assert all(image_closed(crop) for crop in components.encoder_instance.crops)
    assert components.encoder_instance.crops[0].size == (20, 30)
    assert steps[3].message == f"Embedding {DIMENSION} chiều."


def image_closed(image):
    try:
        image.getpixel((0, 0))
    except (ValueError, AttributeError):
        return True
    return False


def test_source_failure_is_reported_on_source_only():
    def opener(target, cancelled):
        raise AIWorkerError(AIErrorCode.SOURCE_OPEN_FAILED, internal_detail="rtsp://u:p@h")

    components = Components()
    subject, _ = diagnostics(components, opener=opener)

    steps = subject.camera_pipeline(camera(), CONFIG)

    assert outcomes(steps) == [
        ("FRAME_SOURCE", Outcome.FAILED),
        ("DETECTOR", Outcome.SKIPPED),
        ("TRACKER", Outcome.SKIPPED),
        ("IMAGE_ENCODER", Outcome.SKIPPED),
    ]
    assert steps[0].code == "source_open_failed"
    assert "u:p" not in str([step.as_dict() for step in steps])
    assert components.built == []


def test_forbidden_rtsp_host_message_is_kept():
    def opener(target, cancelled):
        raise ApiError(422, "rtsp_host_forbidden", "Host bị chặn.")

    subject, _ = diagnostics(opener=opener)
    steps = subject.camera_pipeline(camera(), CONFIG)

    assert steps[0].outcome is Outcome.FAILED
    assert (steps[0].message, steps[0].code) == ("Host bị chặn.", "rtsp_host_forbidden")


def test_empty_stream_fails_source():
    subject, _ = diagnostics(opener=lambda target, cancelled: Source(target.id, count=0))
    steps = subject.camera_pipeline(camera(), CONFIG)
    assert (steps[0].outcome, steps[0].code) == (Outcome.FAILED, "source_empty")


def test_camera_without_rtsp_or_sample_video_never_uses_synthetic_frames():
    components = Components()
    subject, _ = diagnostics(components, opener=lambda target, cancelled: None)

    steps = subject.camera_pipeline(camera(rtsp_url=None), CONFIG)

    assert outcomes(steps)[0] == ("FRAME_SOURCE", Outcome.INCONCLUSIVE)
    assert {step.outcome for step in steps[1:]} == {Outcome.SKIPPED}
    assert overall(steps) is Outcome.INCONCLUSIVE
    assert "tổng hợp" in steps[0].message
    assert components.built == []


def test_inactive_or_disabled_camera_fails_before_opening_source():
    opened = []

    def opener(target, cancelled):
        opened.append(target)
        return Source(target.id)

    subject, _ = diagnostics(opener=opener)
    inactive = subject.camera_pipeline(camera(status=CameraStatus.INACTIVE), CONFIG)
    disabled = subject.camera_pipeline(camera(ai_enabled=False), CONFIG)

    assert inactive[0].outcome is Outcome.FAILED and disabled[0].outcome is Outcome.FAILED
    assert opened == []


def test_no_person_is_inconclusive_not_failure():
    components = Components(detector=Detector([], per_frame=0))
    subject, _ = diagnostics(components)

    steps = subject.camera_pipeline(camera(), CONFIG)

    assert outcomes(steps) == [
        ("FRAME_SOURCE", Outcome.SUCCESS),
        ("DETECTOR", Outcome.INCONCLUSIVE),
        ("TRACKER", Outcome.SKIPPED),
        ("IMAGE_ENCODER", Outcome.SKIPPED),
    ]
    assert steps[1].code == "no_person_detected"
    assert overall(steps) is Outcome.INCONCLUSIVE
    assert components.built == ["detector"]


def test_missing_or_unregistered_config_fails_detector_step():
    missing, _ = diagnostics()
    steps = missing.camera_pipeline(camera(), None)
    assert outcomes(steps)[1] == ("DETECTOR", Outcome.FAILED)

    components = Components()
    invalid, _ = diagnostics(components, registry=Registry(ValueError("unknown")))
    steps = invalid.camera_pipeline(camera(), CONFIG)
    assert outcomes(steps)[1:] == [
        ("DETECTOR", Outcome.FAILED),
        ("TRACKER", Outcome.SKIPPED),
        ("IMAGE_ENCODER", Outcome.SKIPPED),
    ]
    assert steps[1].code == "ai_config_invalid"
    assert components.built == []


@pytest.mark.parametrize(
    ("detector", "code"),
    [
        (
            lambda log: Detector(log, open_error=AIWorkerError(AIErrorCode.DETECTOR_UNAVAILABLE)),
            "detector_unavailable",
        ),
        (
            lambda log: Detector(log, error=AIWorkerError(AIErrorCode.DETECTOR_INFERENCE_FAILED)),
            "detector_inference_failed",
        ),
        (lambda log: Detector(log, error=RuntimeError("/secret/model.pt")), "diagnostic_failed"),
    ],
)
def test_detector_failure_is_attributed_to_detector(detector, code):
    components = Components(detector=detector([]))
    subject, _ = diagnostics(components)

    steps = subject.camera_pipeline(camera(), CONFIG)

    assert outcomes(steps)[1:] == [
        ("DETECTOR", Outcome.FAILED),
        ("TRACKER", Outcome.SKIPPED),
        ("IMAGE_ENCODER", Outcome.SKIPPED),
    ]
    assert steps[1].code == code
    assert "secret" not in str([step.as_dict() for step in steps])
    assert ("close", "detector") in components.log


def test_tracker_failure_is_attributed_to_tracker():
    components = Components(
        tracker=Tracker([], error=AIWorkerError(AIErrorCode.TRACKER_INFERENCE_FAILED))
    )
    subject, _ = diagnostics(components)

    steps = subject.camera_pipeline(camera(), CONFIG)

    assert outcomes(steps)[1:] == [
        ("DETECTOR", Outcome.SUCCESS),
        ("TRACKER", Outcome.FAILED),
        ("IMAGE_ENCODER", Outcome.SKIPPED),
    ]
    assert steps[2].code == "tracker_inference_failed"
    assert "encoder" not in components.built


def test_unconfirmed_tracker_is_inconclusive_but_encoder_still_runs_on_best_detection():
    class Mixed(Detector):
        def detect(self, frame):
            self.frames.append(frame)
            if frame.sample_sequence == 2:
                return (detection(x=30, confidence=0.95), detection(x=5, confidence=0.4))
            return (detection(x=12, confidence=0.5),)

    components = Components(detector=Mixed([]), tracker=Tracker([], confirm=False))
    subject, _ = diagnostics(components)

    steps = subject.camera_pipeline(camera(), CONFIG)

    assert outcomes(steps)[2:] == [
        ("TRACKER", Outcome.INCONCLUSIVE),
        ("IMAGE_ENCODER", Outcome.SUCCESS),
    ]
    assert steps[2].code == "no_confirmed_track"
    crop = components.encoder_instance.crops[0]
    assert crop.size == (20, 30)


@pytest.mark.parametrize(
    ("encoder", "code"),
    [
        (
            lambda log: Encoder(
                log, open_error=AIWorkerError(AIErrorCode.IMAGE_ENCODER_UNAVAILABLE)
            ),
            "image_encoder_unavailable",
        ),
        (
            lambda log: Encoder(
                log, error=AIWorkerError(AIErrorCode.IMAGE_ENCODER_INFERENCE_FAILED)
            ),
            "image_encoder_inference_failed",
        ),
    ],
)
def test_image_encoder_failure_is_attributed_to_encoder(encoder, code):
    components = Components(encoder=encoder([]))
    subject, _ = diagnostics(components)

    steps = subject.camera_pipeline(camera(), CONFIG)

    assert outcomes(steps)[1:] == [
        ("DETECTOR", Outcome.SUCCESS),
        ("TRACKER", Outcome.SUCCESS),
        ("IMAGE_ENCODER", Outcome.FAILED),
    ]
    assert steps[3].code == code


def test_image_encoder_dimension_mismatch_fails():
    config = SimpleNamespace(**{**vars(CONFIG), "encoder_dimension": 8})
    subject, _ = diagnostics()
    steps = subject.camera_pipeline(camera(), config)
    assert steps[3].outcome is Outcome.FAILED
    assert steps[3].code == "image_encoder_output_invalid"


def test_deadline_fails_the_running_component_and_cleans_up():
    clock = Clock()
    components = Components()
    components.detector_instance.on_detect = lambda: setattr(clock, "value", 1000.0)
    subject, sources = diagnostics(components, clock=clock, deadline_seconds=10)

    steps = subject.camera_pipeline(camera(), CONFIG)

    assert outcomes(steps)[1:] == [
        ("DETECTOR", Outcome.FAILED),
        ("TRACKER", Outcome.SKIPPED),
        ("IMAGE_ENCODER", Outcome.SKIPPED),
    ]
    assert steps[1].code == "diagnostic_timeout"
    assert ("close", "detector") in components.log
    assert all(image_closed(image) for image in sources[0].images)


def test_source_deadline_is_reported_as_timeout():
    clock = Clock()

    class Slow(Source):
        def __iter__(self):
            for frame in super().__iter__():
                clock.value += 100
                yield frame

    subject, _ = diagnostics(
        opener=lambda target, cancelled: Slow(target.id),
        clock=clock,
        deadline_seconds=150,
    )
    steps = subject.camera_pipeline(camera(), CONFIG)
    assert (steps[0].outcome, steps[0].code) == (Outcome.FAILED, "diagnostic_timeout")


def test_cancelled_source_maps_to_timeout():
    def opener(target, cancelled):
        raise AIWorkerError(AIErrorCode.CANCELLED)

    subject, _ = diagnostics(opener=opener)
    steps = subject.camera_pipeline(camera(), CONFIG)
    assert steps[0].code == "diagnostic_timeout"


def test_only_one_diagnostic_runs_at_a_time():
    subject, _ = diagnostics()
    assert subject._lock.acquire(blocking=False)
    try:
        with pytest.raises(DiagnosticBusyError):
            subject.camera_pipeline(camera(), CONFIG)
        with pytest.raises(DiagnosticBusyError):
            subject.search_components(CONFIG)
    finally:
        subject._lock.release()
    assert subject.camera_pipeline(camera(), CONFIG)[0].outcome is Outcome.SUCCESS


class Gateway:
    def __init__(self, *, image_error=None, text_error=None, values=UNIT, open_error=None):
        self.image_error = image_error
        self.text_error = text_error
        self.values = values
        self.open_error = open_error
        self.calls = []
        self.opened = False
        self.closed = False

    def open(self):
        self.opened = True
        if self.open_error is not None:
            raise self.open_error

    def image(self, content, *, version, dimension):
        self.calls.append(("image", version, dimension))
        Image.open(io.BytesIO(content)).verify()
        if self.image_error is not None:
            raise self.image_error
        return list(self.values)

    def text(self, text, *, version, dimension):
        self.calls.append(("text", text, version, dimension))
        if self.text_error is not None:
            raise self.text_error
        return list(self.values)

    def close(self):
        self.closed = True


def test_search_components_run_real_query_gateway_once():
    gateway = Gateway()
    components = Components(gateways=[gateway])
    subject, _ = diagnostics(components)

    steps = subject.search_components(CONFIG)

    assert outcomes(steps) == [
        ("IMAGE_ENCODER", Outcome.SUCCESS),
        ("TEXT_ENCODER", Outcome.SUCCESS),
    ]
    assert components.built == ["gateway"]
    assert gateway.calls == [
        ("image", "rasa_v1", DIMENSION),
        ("text", DIAGNOSTIC_TEXT, "rasa_v1", DIMENSION),
    ]
    assert gateway.opened and gateway.closed


def test_search_image_failure_does_not_hide_text_encoder_result():
    broken = Gateway(image_error=AIWorkerError(AIErrorCode.IMAGE_ENCODER_INFERENCE_FAILED))
    fresh = Gateway()
    components = Components(gateways=[broken, fresh])
    subject, _ = diagnostics(components)

    steps = subject.search_components(CONFIG)

    assert outcomes(steps) == [
        ("IMAGE_ENCODER", Outcome.FAILED),
        ("TEXT_ENCODER", Outcome.SUCCESS),
    ]
    assert steps[0].code == "image_encoder_inference_failed"
    assert broken.closed and fresh.closed
    assert components.built == ["gateway", "gateway"]


def test_search_text_failure_and_invalid_output():
    components = Components(
        gateways=[Gateway(text_error=AIWorkerError(AIErrorCode.TEXT_ENCODER_INFERENCE_FAILED))]
    )
    subject, _ = diagnostics(components)
    steps = subject.search_components(CONFIG)
    assert outcomes(steps) == [
        ("IMAGE_ENCODER", Outcome.SUCCESS),
        ("TEXT_ENCODER", Outcome.FAILED),
    ]
    assert steps[1].code == "text_encoder_inference_failed"

    invalid, _ = diagnostics(Components(gateways=[Gateway(values=(0.5, 0.5, 0.0, 0.0))]))
    steps = invalid.search_components(CONFIG)
    assert [step.code for step in steps] == [
        "image_encoder_output_invalid",
        "text_encoder_output_invalid",
    ]


def test_search_load_failure_marks_both_encoders_failed():
    components = Components(
        gateways=[
            Gateway(open_error=AIWorkerError(AIErrorCode.IMAGE_ENCODER_UNAVAILABLE)),
            Gateway(open_error=AIWorkerError(AIErrorCode.IMAGE_ENCODER_UNAVAILABLE)),
        ]
    )
    subject, _ = diagnostics(components)
    steps = subject.search_components(CONFIG)
    assert {step.outcome for step in steps} == {Outcome.FAILED}
    assert {step.code for step in steps} == {"image_encoder_unavailable"}


def test_search_config_mismatch_does_not_load_models():
    components = Components()
    subject, _ = diagnostics(components, registry=Registry(ValueError("mismatch")))
    steps = subject.search_components(CONFIG)
    assert {step.code for step in steps} == {"ai_config_invalid"}
    assert components.built == []


def test_search_fixture_is_safe_decodable_png():
    content = search_fixture_image()
    with Image.open(io.BytesIO(content)) as image:
        assert image.format == "PNG" and image.size == (128, 256)


def test_settings_validation():
    with pytest.raises(ValueError):
        DiagnosticSettings(frame_stride=0)
    with pytest.raises(ValueError):
        DiagnosticSettings(sample_frames=10, max_source_frames=5)
    with pytest.raises(ValueError):
        DiagnosticSettings(deadline_seconds=math.inf)


def test_source_opener_uses_bounded_rtsp_and_optional_sample_video(tmp_path):
    created = []

    class FakeRtsp:
        def __init__(self, **kwargs):
            created.append(("rtsp", kwargs))

        def open(self, url, *, camera_id):
            created.append(("open", url, camera_id))
            return "rtsp-source"

    class FakeFile:
        def __init__(self, **kwargs):
            created.append(("file", kwargs))

        def open(self, path, *, camera_id):
            created.append(("open", path, camera_id))
            return "file-source"

    runtime = SimpleNamespace(connection_url=lambda url, secret: url)
    settings = DiagnosticSettings(rtsp_connect_timeout=3, rtsp_read_timeout=4)
    cancelled = lambda: False  # noqa: E731
    video = Path(tmp_path / "sample.mp4")

    opener = camera_source_opener(
        runtime, settings, sample_video=video, rtsp_factory=FakeRtsp, file_factory=FakeFile
    )
    rtsp_camera = camera()
    assert opener(rtsp_camera, cancelled) == "rtsp-source"
    kwargs = created[0][1]
    assert kwargs["encrypted_secret"] == "encrypted-token"
    assert kwargs["access_resolver"] is runtime.connection_url
    assert kwargs["max_reconnects"] == 0
    assert (kwargs["connect_timeout"], kwargs["read_timeout"]) == (3, 4)
    assert kwargs["cancelled"] is cancelled
    assert created[1] == ("open", "rtsp://10.0.0.5/stream", rtsp_camera.id)

    file_camera = camera(rtsp_url=None)
    assert opener(file_camera, cancelled) == "file-source"
    assert created[-1] == ("open", video, file_camera.id)

    without_video = camera_source_opener(runtime, settings, rtsp_factory=FakeRtsp)
    assert without_video(file_camera, cancelled) is None


class ReadOnlyWork:
    def __init__(self, target):
        self.repositories = SimpleNamespace(
            cameras=SimpleNamespace(get=lambda _: target),
            ai_configs=SimpleNamespace(active=lambda: CONFIG),
        )

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return None


def test_monitoring_camera_pipeline_uses_production_runner_without_persisting():
    target = camera()
    subject, _ = diagnostics()
    service = MonitoringService(
        lambda: ReadOnlyWork(target),
        health=SimpleNamespace(check=lambda: SimpleNamespace(components={})),
        search=None,
        runtime=None,
        diagnostics=subject,
    )

    report = service.camera_pipeline(target.id)

    assert report["overall"] == "SUCCESS"
    assert [step["component"] for step in report["steps"]] == [
        "FRAME_SOURCE",
        "DETECTOR",
        "TRACKER",
        "IMAGE_ENCODER",
    ]
    assert all("code" in step for step in report["steps"])
    assert not hasattr(ReadOnlyWork(target), "commit")


def test_monitoring_maps_busy_runner_to_conflict():
    target = camera()
    subject, _ = diagnostics()
    service = MonitoringService(
        lambda: ReadOnlyWork(target),
        health=SimpleNamespace(check=lambda: SimpleNamespace(components={})),
        search=SimpleNamespace(active_config=lambda: CONFIG),
        runtime=None,
        diagnostics=subject,
    )
    subject._lock.acquire()
    try:
        with pytest.raises(ApiError) as caught:
            service.camera_pipeline(target.id)
        assert (caught.value.status, caught.value.code) == (409, "diagnostics_busy")
        with pytest.raises(ApiError):
            service.search_components()
    finally:
        subject._lock.release()


def test_monitoring_search_components_use_production_runner():
    subject, _ = diagnostics(Components(gateways=[Gateway()]))
    service = MonitoringService(
        lambda: None,
        health=SimpleNamespace(
            check=lambda: SimpleNamespace(components={"postgres": {"status": "ok"}})
        ),
        search=SimpleNamespace(active_config=lambda: CONFIG),
        runtime=None,
        diagnostics=subject,
    )

    report = service.search_components()

    assert [(step["component"], step["outcome"]) for step in report["steps"]] == [
        ("ACTIVE_CONFIG", "SUCCESS"),
        ("IMAGE_ENCODER", "SUCCESS"),
        ("TEXT_ENCODER", "SUCCESS"),
        ("STORAGE_POSTGRES", "SUCCESS"),
    ]
