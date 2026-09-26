"""Shared streaming lifecycle and validation for FILE and RTSP frame sources."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable, Iterator
from pathlib import Path
from types import TracebackType
from typing import Self
from uuid import UUID

from PIL import Image, ImageOps

from person_search.workers.contracts import (
    FrameSourceMetadata,
    IdempotentCloseMixin,
    SourceFrame,
    SourceKind,
)
from person_search.workers.errors import AIErrorCode, AIWorkerError


class FrameSourceStateError(RuntimeError):
    """Raised for programmer errors in the open/read/close lifecycle."""


def normalize_source_image(image: Image.Image, *, max_pixels: int) -> Image.Image:
    """Apply EXIF orientation, detach decoder buffers, and expose RGB pixels."""

    if not isinstance(image, Image.Image):
        raise ValueError("Decoded frame must be a PIL image.")
    if isinstance(max_pixels, bool) or not isinstance(max_pixels, int) or max_pixels < 1:
        raise ValueError("max_pixels must be a positive integer.")
    normalized = ImageOps.exif_transpose(image)
    if normalized.width * normalized.height > max_pixels:
        raise ValueError("Decoded frame exceeds the configured pixel limit.")
    if normalized.mode != "RGB":
        normalized = normalized.convert("RGB")
    return normalized.copy()


def source_frame(
    *,
    camera_id: UUID,
    source_frame_index: int,
    source_timestamp_ms: int,
    image: Image.Image,
    max_pixels: int,
) -> SourceFrame:
    """Build one normalized SourceFrame without retaining a decoder-owned image buffer."""

    normalized = normalize_source_image(image, max_pixels=max_pixels)
    return SourceFrame(
        camera_id=camera_id,
        source_frame_index=source_frame_index,
        source_timestamp_ms=source_timestamp_ms,
        image=normalized,
        width=normalized.width,
        height=normalized.height,
    )


class BaseFrameSource(IdempotentCloseMixin, ABC):
    """One-shot, pull-based source that never buffers the complete stream in memory."""

    def __init__(
        self,
        kind: SourceKind,
        *,
        cancelled: Callable[[], bool] | None = None,
    ) -> None:
        if not isinstance(kind, SourceKind):
            raise ValueError("kind must be a SourceKind value.")
        self._kind = kind
        self._cancelled = cancelled or (lambda: False)
        self._metadata: FrameSourceMetadata | None = None
        self._opened = False
        self._eof = False
        self._last_frame_index: int | None = None
        self._last_timestamp_ms: int | None = None

    @property
    def metadata(self) -> FrameSourceMetadata:
        if self._metadata is None:
            raise FrameSourceStateError("Frame source is not open.")
        return self._metadata

    def open(self, source: str | Path, *, camera_id: UUID) -> Self:
        if self._opened or self.closed:
            raise FrameSourceStateError("Frame source instances are one-shot.")
        metadata = FrameSourceMetadata(self._kind, camera_id)
        try:
            self._open_source(source, camera_id=camera_id)
        except Exception as exc:
            try:
                self.close()
            finally:
                if isinstance(exc, AIWorkerError):
                    raise
                raise AIWorkerError(AIErrorCode.SOURCE_OPEN_FAILED, cause=exc) from exc
        self._metadata = metadata
        self._opened = True
        return self

    def read(self) -> SourceFrame | None:
        if not self._opened:
            raise FrameSourceStateError("Frame source must be opened before read().")
        if self.closed:
            raise FrameSourceStateError("Frame source is closed.")
        if self._eof:
            return None
        self._raise_if_cancelled()
        try:
            frame = self._read_source()
        except Exception as exc:
            self.close()
            if isinstance(exc, AIWorkerError):
                raise
            raise AIWorkerError(AIErrorCode.SOURCE_READ_FAILED, cause=exc) from exc
        self._raise_if_cancelled()
        if frame is None:
            self._eof = True
            return None
        try:
            self._validate_frame(frame)
        except (TypeError, ValueError) as exc:
            self.close()
            raise AIWorkerError(AIErrorCode.SOURCE_INVALID_FRAME, cause=exc) from exc
        self._last_frame_index = frame.source_frame_index
        self._last_timestamp_ms = frame.source_timestamp_ms
        return frame

    def __iter__(self) -> Iterator[SourceFrame]:
        while (frame := self.read()) is not None:
            yield frame

    def __enter__(self) -> Self:
        if not self._opened or self.closed:
            raise FrameSourceStateError("Open the frame source before entering its context.")
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.close()

    def _raise_if_cancelled(self) -> None:
        if self._cancelled():
            self.close()
            raise AIWorkerError(AIErrorCode.CANCELLED)

    def _validate_frame(self, frame: object) -> None:
        if not isinstance(frame, SourceFrame):
            raise TypeError("Frame source must return SourceFrame values.")
        if frame.camera_id != self.metadata.camera_id:
            raise ValueError("Frame camera does not match the opened source.")
        expected_index = 0 if self._last_frame_index is None else self._last_frame_index + 1
        if frame.source_frame_index != expected_index:
            raise ValueError("Source frame index must start at zero and increase by one.")
        if (
            self._last_timestamp_ms is not None
            and frame.source_timestamp_ms < self._last_timestamp_ms
        ):
            raise ValueError("Source timestamps must not decrease.")

    def _close(self) -> None:
        self._close_source()

    @abstractmethod
    def _open_source(self, source: str | Path, *, camera_id: UUID) -> None:
        """Acquire the decoder or socket without decoding the complete source."""

    @abstractmethod
    def _read_source(self) -> SourceFrame | None:
        """Decode at most one frame, returning None only for end-of-stream."""

    @abstractmethod
    def _close_source(self) -> None:
        """Release decoder/socket resources; implementations must tolerate partial open."""
