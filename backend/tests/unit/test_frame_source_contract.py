"""Contract tests shared by future FILE and RTSP frame-source adapters."""

from __future__ import annotations

import uuid
from pathlib import Path

import pytest
from PIL import Image

from person_search.workers.contracts import FrameSource, SourceFrame, SourceKind
from person_search.workers.errors import AIErrorCode, AIWorkerError
from person_search.workers.sources import (
    BaseFrameSource,
    FrameSourceStateError,
    normalize_source_image,
    source_frame,
)

pytestmark = [pytest.mark.unit, pytest.mark.contract]


def _frame(camera_id: uuid.UUID, index: int, timestamp_ms: int) -> SourceFrame:
    return source_frame(
        camera_id=camera_id,
        source_frame_index=index,
        source_timestamp_ms=timestamp_ms,
        image=Image.new("RGB", (8, 6), (index, 20, 30)),
        max_pixels=100,
    )


class StubFrameSource(BaseFrameSource):
    def __init__(self, kind: SourceKind, items, *, cancelled=None, open_error=None):
        super().__init__(kind, cancelled=cancelled)
        self.items = list(items)
        self.position = 0
        self.open_error = open_error
        self.opened_locator = None
        self.read_calls = 0
        self.close_calls = 0

    def _open_source(self, source: str | Path, *, camera_id: uuid.UUID) -> None:
        self.opened_locator = source
        if self.open_error is not None:
            raise self.open_error

    def _read_source(self):
        self.read_calls += 1
        if self.position == len(self.items):
            return None
        item = self.items[self.position]
        self.position += 1
        return item

    def _close_source(self) -> None:
        self.close_calls += 1


def test_file_and_rtsp_sources_share_streaming_iterator_contract() -> None:
    camera_id = uuid.uuid4()

    def consume(kind: SourceKind):
        source = StubFrameSource(
            kind,
            [_frame(camera_id, 0, 0), _frame(camera_id, 1, 40)],
        )
        assert isinstance(source, FrameSource)
        opened = source.open("opaque-source", camera_id=camera_id)
        assert source.read_calls == 0
        with opened as frames:
            output = [(frame.source_frame_index, frame.source_timestamp_ms) for frame in frames]
        return source, output

    file_source, file_output = consume(SourceKind.FILE)
    rtsp_source, rtsp_output = consume(SourceKind.RTSP)

    assert file_output == rtsp_output == [(0, 0), (1, 40)]
    assert file_source.metadata.kind is SourceKind.FILE
    assert rtsp_source.metadata.kind is SourceKind.RTSP
    assert file_source.read_calls == rtsp_source.read_calls == 3
    assert file_source.close_calls == rtsp_source.close_calls == 1


def test_empty_source_reaches_stable_end_of_stream_without_buffering() -> None:
    source = StubFrameSource(SourceKind.FILE, []).open("empty", camera_id=uuid.uuid4())

    assert source.read() is None
    assert source.read() is None
    assert source.read_calls == 1
    source.close()
    source.close()
    assert source.close_calls == 1


def test_invalid_frame_and_decreasing_timestamp_fail_closed() -> None:
    camera_id = uuid.uuid4()
    invalid = StubFrameSource(SourceKind.FILE, [object()]).open("bad", camera_id=camera_id)
    with pytest.raises(AIWorkerError) as invalid_error:
        invalid.read()
    assert invalid_error.value.code is AIErrorCode.SOURCE_INVALID_FRAME
    assert invalid.closed is True

    timeline = StubFrameSource(
        SourceKind.RTSP,
        [_frame(camera_id, 0, 40), _frame(camera_id, 1, 39)],
    ).open("timeline", camera_id=camera_id)
    assert timeline.read() is not None
    with pytest.raises(AIWorkerError) as timeline_error:
        timeline.read()
    assert timeline_error.value.code is AIErrorCode.SOURCE_INVALID_FRAME
    assert timeline.closed is True


def test_cancellation_closes_source_and_uses_sanitized_error() -> None:
    camera_id = uuid.uuid4()
    cancelled = False
    source = StubFrameSource(
        SourceKind.RTSP,
        [_frame(camera_id, 0, 0)],
        cancelled=lambda: cancelled,
    ).open("rtsp://secret@camera", camera_id=camera_id)
    cancelled = True

    with pytest.raises(AIWorkerError) as caught:
        source.read()

    assert caught.value.code is AIErrorCode.CANCELLED
    assert caught.value.to_public_dict()["message"] == "Processing was cancelled."
    assert source.closed is True
    assert source.close_calls == 1


def test_open_and_read_failures_release_partially_opened_resources() -> None:
    failed_open = StubFrameSource(
        SourceKind.FILE,
        [],
        open_error=OSError("private path"),
    )
    with pytest.raises(AIWorkerError) as open_error:
        failed_open.open("private", camera_id=uuid.uuid4())
    assert open_error.value.code is AIErrorCode.SOURCE_OPEN_FAILED
    assert failed_open.close_calls == 1

    class ReadFailure(StubFrameSource):
        def _read_source(self):
            raise OSError("decoder detail")

    failed_read = ReadFailure(SourceKind.FILE, []).open("private", camera_id=uuid.uuid4())
    with pytest.raises(AIWorkerError) as read_error:
        failed_read.read()
    assert read_error.value.code is AIErrorCode.SOURCE_READ_FAILED
    assert failed_read.close_calls == 1


def test_lifecycle_rejects_read_before_open_and_reopen_after_close() -> None:
    source = StubFrameSource(SourceKind.FILE, [])
    with pytest.raises(FrameSourceStateError, match="opened before"):
        source.read()
    with pytest.raises(FrameSourceStateError, match="before entering"):
        source.__enter__()

    source.open("one", camera_id=uuid.uuid4())
    source.close()
    with pytest.raises(FrameSourceStateError, match="one-shot"):
        source.open("two", camera_id=uuid.uuid4())


def test_image_policy_normalizes_orientation_and_rgb() -> None:
    image = Image.new("L", (2, 3), 128)
    image.getexif()[274] = 6

    normalized = normalize_source_image(image, max_pixels=6)

    assert normalized.mode == "RGB"
    assert normalized.size == (3, 2)
    assert normalized is not image
    with pytest.raises(ValueError, match="pixel limit"):
        normalize_source_image(image, max_pixels=5)
