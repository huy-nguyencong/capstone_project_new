from __future__ import annotations

import uuid

import pytest
from PIL import Image, ImageDraw

from person_search.ai.selectors import RepresentativeFrameSelector, SelectorSettings
from person_search.storage.contracts import BoundingBoxPixels
from person_search.workers.contracts import (
    Detection,
    EmbeddingVector,
    ModelLineage,
    SourceFrame,
    TrackState,
    TrackUpdate,
)
from person_search.workers.errors import AIErrorCode, AIWorkerError
from person_search.workers.production import ProductionPipeline

pytestmark = pytest.mark.unit

SHA = "c" * 64


def lineage(name):
    return ModelLineage(name, "1", SHA)


DETECTOR = lineage("detector")
TRACKER = lineage("tracker")
ENCODER = lineage("encoder")


class Component:
    def __init__(self, *, open_error=None):
        self.opened = False
        self.closed = False
        self.open_error = open_error

    def open(self):
        if self.open_error:
            raise self.open_error
        self.opened = True

    def close(self):
        self.closed = True


class Detector(Component):
    lineage = DETECTOR

    def __init__(self, *, empty=False, error=None):
        super().__init__()
        self.empty = empty
        self.error = error

    def detect(self, frame):
        if self.error:
            raise self.error
        if self.empty:
            return ()
        return (
            Detection(
                BoundingBoxPixels(15, 10, 30, 70, frame.width, frame.height),
                0,
                "person",
                0.9,
                DETECTOR,
            ),
        )


class Tracker(Component):
    lineage = TRACKER

    def __init__(self, *, error=None):
        super().__init__()
        self.error = error
        self.last = None

    def update(self, frame, detections):
        if self.error:
            raise self.error
        if not detections:
            return ()
        self.last = frame
        return (
            TrackUpdate(
                "track-1",
                frame.camera_id,
                detections[0].bbox,
                frame.source_frame_index,
                frame.source_timestamp_ms,
                TrackState.ACTIVE,
                TRACKER,
            ),
        )

    def flush(self):
        if self.last is None:
            return ()
        return (
            TrackUpdate(
                "track-1",
                self.last.camera_id,
                BoundingBoxPixels(15, 10, 30, 70, self.last.width, self.last.height),
                self.last.source_frame_index,
                self.last.source_timestamp_ms,
                TrackState.ENDED,
                TRACKER,
            ),
        )


class Encoder(Component):
    lineage = ENCODER

    def __init__(self, *, error=None):
        super().__init__()
        self.error = error
        self.seen_sizes = []

    def encode(self, image):
        if self.error:
            raise self.error
        self.seen_sizes.append(image.size)
        return EmbeddingVector((1.0,) + (0.0,) * 255, 256, True, ENCODER)


def frames(count=3):
    camera_id = uuid.uuid4()
    result = []
    for index in range(count):
        image = Image.new("RGB", (80, 100), "white")
        draw = ImageDraw.Draw(image)
        for x in range(0, 80, 4):
            draw.line((x, 0, x, 99), fill="black")
        result.append(SourceFrame(camera_id, index, index * 40, image, 80, 100))
    return result


def pipeline(*, detector=None, tracker=None, encoder=None, cancelled=lambda: False, clock=None):
    detector = detector or Detector()
    tracker = tracker or Tracker()
    encoder = encoder or Encoder()
    selector = RepresentativeFrameSelector(
        processing_job_id=uuid.uuid4(),
        ai_config_version_id=uuid.uuid4(),
        detector=DETECTOR,
        tracker=TRACKER,
        encoder=ENCODER,
        settings=SelectorSettings(
            minimum_bbox_width=8,
            minimum_bbox_height=8,
            minimum_sharpness_variance=0.01,
        ),
    )
    kwargs = {"clock": clock} if clock else {}
    return (
        ProductionPipeline(
            detector,
            tracker,
            selector,
            encoder,
            sampling_interval=1,
            job_timeout_seconds=30,
            cancelled=cancelled,
            **kwargs,
        ),
        (detector, tracker, selector, encoder),
    )


def assert_closed(components):
    assert all(
        component.closed if hasattr(component, "closed") else component._closed
        for component in components
    )


def test_happy_path_flushes_eof_and_returns_real_contract_embedding():
    subject, components = pipeline()
    source = frames()
    result = subject.run(source)

    assert result.source_frames == 3
    assert result.sampled_frames == 3
    assert result.detections == 3
    assert result.track_updates == 4
    assert len(result.encoded_tracks) == 1
    assert result.encoded_tracks[0].embedding.encoder == ENCODER
    assert {timing.stage for timing in result.timings} >= {
        "load",
        "sampling",
        "detector",
        "tracker",
        "selector",
        "image_encoder",
    }
    assert_closed(components)
    result.encoded_tracks[0].track.representative.frame.image.close()


def test_zero_detection_succeeds_without_completed_tracks():
    subject, components = pipeline(detector=Detector(empty=True))
    result = subject.run(frames(2))
    assert result.detections == 0
    assert result.encoded_tracks == ()
    assert_closed(components)


def test_stage_failure_is_preserved_and_all_resources_close():
    failure = AIWorkerError(AIErrorCode.DETECTOR_INFERENCE_FAILED)
    subject, components = pipeline(detector=Detector(error=failure))
    with pytest.raises(AIWorkerError) as caught:
        subject.run(frames(1))
    assert caught.value.code is AIErrorCode.DETECTOR_INFERENCE_FAILED
    assert_closed(components)


def test_model_load_failure_closes_components_that_were_already_opened():
    tracker = Tracker()
    tracker.open_error = AIWorkerError(AIErrorCode.TRACKER_INFERENCE_FAILED)
    subject, components = pipeline(tracker=tracker)
    with pytest.raises(AIWorkerError) as caught:
        subject.run(frames(1))
    assert caught.value.code is AIErrorCode.TRACKER_INFERENCE_FAILED
    assert components[0].closed
    assert not tracker.opened


def test_tracker_and_encoder_failures_keep_their_stage_codes():
    tracker_failure = AIWorkerError(AIErrorCode.TRACKER_INFERENCE_FAILED)
    subject, components = pipeline(tracker=Tracker(error=tracker_failure))
    with pytest.raises(AIWorkerError) as caught:
        subject.run(frames(1))
    assert caught.value.code is AIErrorCode.TRACKER_INFERENCE_FAILED
    assert_closed(components)

    encoder_failure = AIWorkerError(AIErrorCode.IMAGE_ENCODER_INFERENCE_FAILED)
    subject, components = pipeline(encoder=Encoder(error=encoder_failure))
    with pytest.raises(AIWorkerError) as caught:
        subject.run(frames(1))
    assert caught.value.code is AIErrorCode.IMAGE_ENCODER_INFERENCE_FAILED
    assert_closed(components)


def test_cancel_drops_active_track_and_closes_buffered_frames():
    checks = iter((False, False, True))
    subject, components = pipeline(cancelled=lambda: next(checks, True))
    with pytest.raises(AIWorkerError) as caught:
        subject.run(frames(3))
    assert caught.value.code is AIErrorCode.CANCELLED
    assert_closed(components)


def test_job_deadline_fails_closed_and_cleans_up():
    moments = iter((0.0, 0.0, 0.0, 31.0, 31.0, 31.0, 31.0, 31.0))
    subject, components = pipeline(clock=lambda: next(moments, 31.0))
    with pytest.raises(AIWorkerError) as caught:
        subject.run(frames(1))
    assert caught.value.code is AIErrorCode.RESOURCE_EXHAUSTED
    assert_closed(components)
