"""RTSP frames are timestamped from the stream's PTS, anchored to the machine clock per session."""

from __future__ import annotations

import uuid
from fractions import Fraction
from types import SimpleNamespace

import pytest
from PIL import Image

from person_search.workers.sources import RtspFrameSource

pytestmark = pytest.mark.unit

TIME_BASE = Fraction(1, 90_000)  # RTP clock of H.264


class DecodedFrame:
    def __init__(self, pts=None, time_base=TIME_BASE):
        self.image = Image.new("RGB", (8, 6), (10, 20, 30))
        self.pts = pts
        self.time_base = time_base

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


def _source(container_or_containers, clock, **kwargs):
    containers = (
        iter(container_or_containers)
        if isinstance(container_or_containers, list)
        else iter([container_or_containers])
    )
    return RtspFrameSource(
        access_resolver=_resolver,
        opener=lambda *args, **options: next(containers),
        clock=clock,
        max_reconnects=kwargs.pop("max_reconnects", 0),
        backoff_seconds=0,
        **kwargs,
    ).open("rtsp://10.0.0.1/live", camera_id=uuid.uuid4())


def test_timestamps_follow_the_stream_clock_not_the_processing_speed() -> None:
    # Three consecutive 60 fps frames (1,500 ticks apart) read by a machine that needs
    # 0.5, 2.0 and 2.4 seconds per frame.
    frames = [DecodedFrame(pts=900_000 + 1_500 * i) for i in range(3)]
    source = _source(FakeContainer(frames), _clock(100.0, 100.5, 102.5, 104.9))

    with source:
        stamps = [source.read().source_timestamp_ms for _ in range(3)]

    assert stamps == [500, 517, 533]
    assert source.timestamp_mode == "stream"
    assert source.timeline_anchors == 1
    assert source.timestamp_fallback_frames == 0


def test_clock_mode_keeps_the_reception_time_behaviour() -> None:
    frames = [DecodedFrame(pts=1_500 * i) for i in range(3)]
    source = _source(FakeContainer(frames), _clock(0.0, 0.04, 0.08, 0.12), timestamp_mode="clock")

    with source:
        stamps = [source.read().source_timestamp_ms for _ in range(3)]

    assert stamps == [40, 80, 120]
    assert source.timestamp_fallback_frames == 3


def test_frames_without_pts_fall_back_to_the_clock_and_stay_monotonic() -> None:
    frames = [DecodedFrame(pts=0), DecodedFrame(pts=None), DecodedFrame(pts=3_000)]
    # Clock: open at 0; frame 0 at 0.1; frame 1 (no PTS) at 0.9; frame 2 at 1.0.
    source = _source(FakeContainer(frames), _clock(0.0, 0.1, 0.9, 1.0))

    with source:
        stamps = [source.read().source_timestamp_ms for _ in range(3)]

    # Stream clock: 100 (anchor), then no PTS -> clock 900, then 100 + 33 = 133 -> clamped to 900.
    assert stamps == [100, 900, 900]
    assert source.timestamp_fallback_frames == 1


def test_stream_clock_going_backwards_is_anchored_again_after_the_last_frame() -> None:
    frames = [DecodedFrame(pts=9_000_000), DecodedFrame(pts=9_001_500), DecodedFrame(pts=0)]
    source = _source(FakeContainer(frames), _clock(0.0, 0.1, 0.2, 0.3))

    with source:
        stamps = [source.read().source_timestamp_ms for _ in range(3)]

    assert stamps == [100, 117, 300]
    assert source.timeline_anchors == 2


def test_reconnect_anchors_the_new_session_and_never_goes_back_in_time() -> None:
    def interrupted():
        yield DecodedFrame(pts=5_000_000)
        yield DecodedFrame(pts=5_001_500)
        raise TimeoutError("read timeout")

    first = FakeContainer(interrupted())
    second = FakeContainer([DecodedFrame(pts=100), DecodedFrame(pts=1_600)])
    # Clock: open 0; frames at 0.1, 0.2; timeout; reconnect; next frames read at 5.3, 5.4.
    source = _source([first, second], _clock(0.0, 0.1, 0.2, 5.3, 5.4), max_reconnects=1)

    stamps = [source.read().source_timestamp_ms for _ in range(4)]
    source.close()

    assert stamps == [100, 117, 5300, 5317]
    assert source.reconnects == 1
    assert source.timeline_anchors == 2
    assert first.closed is second.closed is True


def test_invalid_timestamp_mode_is_rejected() -> None:
    with pytest.raises(ValueError, match="timestamp_mode"):
        RtspFrameSource(access_resolver=_resolver, timestamp_mode="rtp")
