from __future__ import annotations

import uuid
from fractions import Fraction
from pathlib import Path
from types import SimpleNamespace

import av
import pytest
from PIL import Image

from person_search.workers.errors import AIErrorCode, AIWorkerError
from person_search.workers.sources import FileFrameSource

pytestmark = pytest.mark.unit


class DecodedFrame:
    def __init__(self, pts, time_base=Fraction(1, 100), color=(10, 20, 30)):
        self.pts = pts
        self.time_base = time_base
        self._image = Image.new("RGB", (8, 6), color)

    def to_image(self):
        return self._image


class FakeContainer:
    def __init__(
        self,
        frames,
        *,
        codec="h264",
        average_rate=25,
        frame_count=0,
        duration=100,
    ):
        self.closed = False
        self.decode_calls = 0
        self.duration = None
        codec_context = SimpleNamespace(name=codec, width=8, height=6)
        stream = SimpleNamespace(
            codec_context=codec_context,
            average_rate=average_rate,
            time_base=Fraction(1, 100),
            frames=frame_count,
            duration=duration,
        )
        self.streams = SimpleNamespace(video=[stream])
        self.format = SimpleNamespace(name="mov,mp4,m4a,3gp,3g2,mj2")
        self._frames = frames

    def decode(self, stream):
        del stream
        self.decode_calls += 1
        return iter(self._frames)

    def close(self):
        self.closed = True


def _mp4_path(tmp_path: Path) -> Path:
    path = tmp_path / "source.mp4"
    path.write_bytes(b"\0\0\0\x18ftypisom" + b"x" * 32)
    return path


def _source(path, container, **options):
    calls = []

    def opener(value, **kwargs):
        calls.append((value, kwargs))
        return container

    source = FileFrameSource(opener=opener, **options).open(path, camera_id=uuid.uuid4())
    return source, calls


@pytest.mark.parametrize("codec", ["h264", "mpeg4"])
def test_codec_probe_and_variable_pts_stream_one_frame_per_read(tmp_path, codec) -> None:
    path = _mp4_path(tmp_path)
    frames = [DecodedFrame(100), DecodedFrame(102), DecodedFrame(107)]
    container = FakeContainer(frames, codec=codec, frame_count=3)

    source, calls = _source(path, container)

    assert container.decode_calls == 1
    assert source.probe.codec_name == codec
    assert source.probe.declared_frame_count == 3
    assert calls == [(str(path.resolve()), {"options": {"protocol_whitelist": "file"}})]
    assert source.read().source_timestamp_ms == 0
    assert source.progress.decoded_frames == 1
    assert source.read().source_timestamp_ms == 20
    assert source.read().source_timestamp_ms == 70
    assert source.read() is None
    assert container.closed is True
    assert source.progress.fraction == 1.0


def test_missing_pts_uses_fps_and_missing_both_fails_closed(tmp_path) -> None:
    path = _mp4_path(tmp_path)
    source, _ = _source(
        path,
        FakeContainer([DecodedFrame(None), DecodedFrame(None)], average_rate=25),
    )

    assert [frame.source_timestamp_ms for frame in source] == [0, 40]
    assert source.progress.timestamp_fallback_frames == 2

    failed_container = FakeContainer([DecodedFrame(None)], average_rate=None)
    failed, _ = _source(path, failed_container)
    with pytest.raises(AIWorkerError) as caught:
        failed.read()
    assert caught.value.code is AIErrorCode.SOURCE_READ_FAILED
    assert failed_container.closed is True


def test_decoder_failure_is_not_reported_as_eof(tmp_path) -> None:
    path = _mp4_path(tmp_path)

    def corrupt_frames():
        yield DecodedFrame(0)
        raise OSError("corrupt packet with private detail")

    container = FakeContainer(corrupt_frames())
    source, _ = _source(path, container)

    assert source.read() is not None
    with pytest.raises(AIWorkerError) as caught:
        source.read()
    assert caught.value.code is AIErrorCode.SOURCE_READ_FAILED
    assert str(caught.value) == "The frame source could not be read."
    assert container.closed is True


def test_changed_file_and_cancellation_release_decoder(tmp_path) -> None:
    path = _mp4_path(tmp_path)
    changed_container = FakeContainer([DecodedFrame(0), DecodedFrame(1)])
    changed, _ = _source(path, changed_container)
    assert changed.read() is not None
    path.write_bytes(path.read_bytes() + b"changed")
    with pytest.raises(AIWorkerError) as changed_error:
        changed.read()
    assert changed_error.value.code is AIErrorCode.SOURCE_READ_FAILED
    assert changed_container.closed is True

    cancelled = False
    cancel_container = FakeContainer([DecodedFrame(0)])
    cancel_source, _ = _source(
        path,
        cancel_container,
        cancelled=lambda: cancelled,
    )
    cancelled = True
    with pytest.raises(AIWorkerError) as cancel_error:
        cancel_source.read()
    assert cancel_error.value.code is AIErrorCode.CANCELLED
    assert cancel_container.closed is True


def test_signature_codec_dimensions_and_byte_limits_are_checked_before_decode(tmp_path) -> None:
    invalid = tmp_path / "invalid.mp4"
    invalid.write_bytes(b"not an mp4")
    with pytest.raises(AIWorkerError) as signature_error:
        FileFrameSource(opener=lambda *args, **kwargs: None).open(
            invalid, camera_id=uuid.uuid4()
        )
    assert signature_error.value.code is AIErrorCode.SOURCE_OPEN_FAILED

    path = _mp4_path(tmp_path)
    unsupported = FakeContainer([], codec="wmv3")
    with pytest.raises(AIWorkerError):
        _source(path, unsupported)
    assert unsupported.closed is True

    oversized = FakeContainer([])
    oversized.streams.video[0].codec_context.width = 4000
    oversized.streams.video[0].codec_context.height = 3000
    with pytest.raises(AIWorkerError):
        _source(path, oversized)
    assert oversized.closed is True

    with pytest.raises(AIWorkerError):
        _source(path, FakeContainer([]), max_bytes=8)


def test_real_mpeg4_video_decodes_sequentially_with_traceable_timeline(tmp_path) -> None:
    path = tmp_path / "real.mp4"
    with av.open(str(path), mode="w") as container:
        stream = container.add_stream("mpeg4", rate=25)
        stream.width = 16
        stream.height = 16
        stream.pix_fmt = "yuv420p"
        for index in range(4):
            frame = av.VideoFrame.from_image(Image.new("RGB", (16, 16), (index * 20, 0, 0)))
            for packet in stream.encode(frame):
                container.mux(packet)
        for packet in stream.encode():
            container.mux(packet)

    source = FileFrameSource().open(path, camera_id=uuid.uuid4())
    with source:
        decoded = list(source)

    assert [frame.source_frame_index for frame in decoded] == [0, 1, 2, 3]
    assert [frame.source_timestamp_ms for frame in decoded] == [0, 40, 80, 120]
    assert all(frame.image.mode == "RGB" for frame in decoded)
    assert source.progress.decoded_frames == 4
