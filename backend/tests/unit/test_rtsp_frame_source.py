from __future__ import annotations

import uuid
from types import SimpleNamespace

import pytest
from cryptography.fernet import Fernet
from PIL import Image

from person_search.demo import DemoDetector, DemoTracker
from person_search.services.camera_runtime import CameraRuntime
from person_search.workers.errors import AIErrorCode, AIWorkerError
from person_search.workers.sampling import FrameSampler
from person_search.workers.sources import RtspFrameSource

pytestmark = pytest.mark.unit


class DecodedFrame:
    def __init__(self, color=(10, 20, 30)):
        self.image = Image.new("RGB", (8, 6), color)

    def to_image(self):
        return self.image


class FakeContainer:
    def __init__(self, frames):
        self.closed = False
        self.streams = SimpleNamespace(
            video=[SimpleNamespace(codec_context=SimpleNamespace(width=8, height=6))]
        )
        self.frames = frames

    def decode(self, stream):
        del stream
        return iter(self.frames)

    def close(self):
        self.closed = True


def _resolver(url, secret):
    assert secret is None
    return url


def _clock(*values):
    readings = iter(values)
    return lambda: next(readings)


def test_live_frames_use_capture_clock_and_the_shared_sampler_contract() -> None:
    container = FakeContainer([DecodedFrame(), DecodedFrame(), DecodedFrame()])
    source = RtspFrameSource(
        access_resolver=_resolver,
        opener=lambda *args, **kwargs: container,
        clock=_clock(100.0, 100.04, 100.08, 100.12),
        max_reconnects=0,
    ).open("rtsp://10.0.0.1/live", camera_id=uuid.uuid4())

    with source:
        frames = [source.read(), source.read(), source.read()]

    assert [frame.source_frame_index for frame in frames] == [0, 1, 2]
    assert [frame.source_timestamp_ms for frame in frames] == [40, 80, 120]
    assert [frame.source_frame_index for frame in FrameSampler.for_benchmark(2).select(frames)] == [
        0,
        2,
    ]
    assert container.closed is True


def test_rtsp_frames_run_through_the_same_detector_tracker_path() -> None:
    container = FakeContainer([DecodedFrame() for _ in range(41)])
    times = [0.0, *(index * 0.04 for index in range(1, 42))]
    source = RtspFrameSource(
        access_resolver=_resolver,
        opener=lambda *args, **kwargs: container,
        clock=_clock(*times),
        max_reconnects=0,
    ).open("rtsp://10.0.0.1/live", camera_id=uuid.uuid4())
    sampler = FrameSampler(10)
    detector, tracker = DemoDetector(), DemoTracker()
    tracks = []

    with source:
        for frame in source:
            sampled = sampler.sample(frame)
            if sampled is not None:
                tracks.extend(tracker.update(sampled, detector.detect(sampled)))
            if frame.source_frame_index == 40:
                break

    assert len(tracks) == 1
    assert tracks[0].representative.source_frame_index == 0
    assert tracks[0].ended_ms == 1640


def test_ssrf_policy_blocks_host_before_decoder_connects() -> None:
    runtime = CameraRuntime(Fernet.generate_key().decode(), ["10.0.0.0/8"])
    opened = []
    source = RtspFrameSource(
        access_resolver=runtime.connection_url,
        opener=lambda *args, **kwargs: opened.append(args),
    )

    with pytest.raises(AIWorkerError) as caught:
        source.open("rtsp://127.0.0.1/live", camera_id=uuid.uuid4())

    assert caught.value.code is AIErrorCode.SOURCE_OPEN_FAILED
    assert opened == []


def test_encrypted_credentials_are_materialized_only_for_open() -> None:
    runtime = CameraRuntime(Fernet.generate_key().decode(), ["10.0.0.0/8"])
    public_url, secret = runtime.split_url("rtsp://admin:secret@10.0.0.1/live")
    opened_urls = []
    container = FakeContainer([DecodedFrame()])

    def opener(url, **kwargs):
        del kwargs
        opened_urls.append(url)
        return container

    source = RtspFrameSource(
        encrypted_secret=secret,
        access_resolver=runtime.connection_url,
        opener=opener,
        clock=_clock(0, 0.1),
        max_reconnects=0,
    ).open(public_url, camera_id=uuid.uuid4())
    source.close()

    assert opened_urls == ["rtsp://admin:secret@10.0.0.1/live"]
    assert source._public_url == "rtsp://10.0.0.1/live"
    assert "secret" not in str(source.metadata)


@pytest.mark.parametrize(
    ("failure", "code"),
    [
        (TimeoutError("connect timeout"), AIErrorCode.SOURCE_CONNECT_TIMEOUT),
        (PermissionError("401 unauthorized"), AIErrorCode.SOURCE_AUTH_FAILED),
    ],
)
def test_connect_timeout_and_bad_credentials_have_distinct_safe_errors(failure, code) -> None:
    def opener(*args, **kwargs):
        raise failure

    source = RtspFrameSource(access_resolver=_resolver, opener=opener)
    with pytest.raises(AIWorkerError) as caught:
        source.open("rtsp://10.0.0.1/live", camera_id=uuid.uuid4())

    assert caught.value.code is code
    assert "10.0.0.1" not in str(caught.value)


def test_read_timeout_reconnects_without_resetting_index_or_leaking_container() -> None:
    def interrupted():
        yield DecodedFrame()
        raise TimeoutError("read timeout")

    first = FakeContainer(interrupted())
    second = FakeContainer([DecodedFrame((30, 20, 10))])
    containers = iter([first, second])
    source = RtspFrameSource(
        access_resolver=_resolver,
        opener=lambda *args, **kwargs: next(containers),
        clock=_clock(0, 0.1, 0.2),
        max_reconnects=1,
        backoff_seconds=0,
    ).open("rtsp://10.0.0.1/live", camera_id=uuid.uuid4())

    first_frame = source.read()
    second_frame = source.read()
    source.close()

    assert (first_frame.source_frame_index, second_frame.source_frame_index) == (0, 1)
    assert (first_frame.source_timestamp_ms, second_frame.source_timestamp_ms) == (100, 200)
    assert source.reconnects == 1
    assert first.closed is second.closed is True


def test_ended_stream_retries_then_reports_terminal_live_source_error() -> None:
    first, second = FakeContainer([]), FakeContainer([])
    containers = iter([first, second])
    source = RtspFrameSource(
        access_resolver=_resolver,
        opener=lambda *args, **kwargs: next(containers),
        clock=_clock(0),
        max_reconnects=1,
        backoff_seconds=0,
    ).open("rtsp://10.0.0.1/live", camera_id=uuid.uuid4())

    with pytest.raises(AIWorkerError) as caught:
        source.read()

    assert caught.value.code is AIErrorCode.SOURCE_STREAM_ENDED
    assert first.closed is second.closed is True
    assert source.closed is True


def test_cancellation_interrupts_backoff_without_opening_another_socket() -> None:
    cancelled = False
    sleeps = []
    opened = []
    container = FakeContainer([])

    def opener(*args, **kwargs):
        opened.append(args)
        return container

    def sleeper(delay):
        nonlocal cancelled
        sleeps.append(delay)
        cancelled = True

    source = RtspFrameSource(
        access_resolver=_resolver,
        opener=opener,
        cancelled=lambda: cancelled,
        clock=_clock(0),
        max_reconnects=3,
        backoff_seconds=1,
        sleeper=sleeper,
    ).open("rtsp://10.0.0.1/live", camera_id=uuid.uuid4())

    with pytest.raises(AIWorkerError) as caught:
        source.read()

    assert caught.value.code is AIErrorCode.CANCELLED
    assert len(opened) == 1
    assert sleeps == [0.05]
    assert container.closed is True
