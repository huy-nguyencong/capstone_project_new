"""Bounded, streaming file-video source backed by PyAV."""

from __future__ import annotations

import math
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path
from typing import Any
from uuid import UUID

import av

from person_search.workers.contracts import SourceFrame, SourceKind
from person_search.workers.sources.base import BaseFrameSource, source_frame

DEFAULT_MAX_VIDEO_BYTES = 500 * 1024 * 1024
DEFAULT_MAX_FRAME_PIXELS = 3840 * 2160
DEFAULT_ALLOWED_CODECS = frozenset({"av1", "h264", "hevc", "mpeg4", "vp8", "vp9"})
_SIGNATURES = {
    ".avi": lambda header: header[:4] == b"RIFF" and header[8:12] == b"AVI ",
    ".mkv": lambda header: header[:4] == b"\x1aE\xdf\xa3",
    ".mp4": lambda header: header[4:8] == b"ftyp",
}


@dataclass(frozen=True, slots=True)
class FileSourceProbe:
    """Validated metadata captured before the first frame is consumed."""

    path: Path
    size_bytes: int
    modified_ns: int
    container_format: str
    codec_name: str
    width: int
    height: int
    average_fps: float | None
    time_base: Fraction | None
    declared_frame_count: int | None
    duration_ms: int | None


@dataclass(frozen=True, slots=True)
class FileSourceProgress:
    decoded_frames: int
    declared_frame_count: int | None
    source_timestamp_ms: int | None
    duration_ms: int | None
    fraction: float | None
    timestamp_fallback_frames: int


def _positive_fraction(value: object) -> Fraction | None:
    if value is None:
        return None
    try:
        result = Fraction(value)
    except (TypeError, ValueError, ZeroDivisionError):
        return None
    return result if result > 0 else None


def _positive_int(value: object) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) and value > 0 else None


class FileFrameSource(BaseFrameSource):
    """Decode one local video frame per ``read`` without buffering the full file."""

    def __init__(
        self,
        *,
        max_bytes: int = DEFAULT_MAX_VIDEO_BYTES,
        max_pixels: int = DEFAULT_MAX_FRAME_PIXELS,
        allowed_codecs: frozenset[str] = DEFAULT_ALLOWED_CODECS,
        cancelled: Callable[[], bool] | None = None,
        opener: Callable[..., Any] = av.open,
    ) -> None:
        super().__init__(SourceKind.FILE, cancelled=cancelled)
        if max_bytes < 1 or max_pixels < 1:
            raise ValueError("File source limits must be positive.")
        if not allowed_codecs:
            raise ValueError("At least one video codec must be allowed.")
        self._max_bytes = max_bytes
        self._max_pixels = max_pixels
        self._allowed_codecs = frozenset(name.lower() for name in allowed_codecs)
        self._opener = opener
        self._path: Path | None = None
        self._container: Any | None = None
        self._frames: Iterator[Any] | None = None
        self._camera_id: UUID | None = None
        self._probe: FileSourceProbe | None = None
        self._next_index = 0
        self._first_pts_seconds: Fraction | None = None
        self._last_timestamp_ms: int | None = None
        self._fallback_frames = 0

    @property
    def probe(self) -> FileSourceProbe:
        if self._probe is None:
            raise RuntimeError("File source has not been probed.")
        return self._probe

    @property
    def progress(self) -> FileSourceProgress:
        probe = self.probe
        frame_fraction = (
            self._next_index / probe.declared_frame_count
            if probe.declared_frame_count is not None
            else None
        )
        time_fraction = (
            self._last_timestamp_ms / probe.duration_ms
            if self._last_timestamp_ms is not None and probe.duration_ms
            else None
        )
        candidates = [value for value in (frame_fraction, time_fraction) if value is not None]
        fraction = min(1.0, max(candidates)) if candidates else None
        return FileSourceProgress(
            decoded_frames=self._next_index,
            declared_frame_count=probe.declared_frame_count,
            source_timestamp_ms=self._last_timestamp_ms,
            duration_ms=probe.duration_ms,
            fraction=fraction,
            timestamp_fallback_frames=self._fallback_frames,
        )

    def _open_source(self, source: str | Path, *, camera_id: UUID) -> None:
        supplied_path = Path(source)
        if supplied_path.is_symlink():
            raise ValueError("Video source must not be a symlink.")
        path = supplied_path.resolve(strict=True)
        if not path.is_file():
            raise ValueError("Video source must be a regular, non-symlink file.")
        suffix = path.suffix.lower()
        signature = _SIGNATURES.get(suffix)
        if signature is None:
            raise ValueError("Video container extension is not supported.")
        stat = path.stat()
        if stat.st_size < 1 or stat.st_size > self._max_bytes:
            raise ValueError("Video source exceeds the configured byte limit.")
        with path.open("rb") as stream:
            header = stream.read(16)
        if not signature(header):
            raise ValueError("Video content does not match its container extension.")

        self._path = path
        self._camera_id = camera_id
        self._container = self._opener(str(path), options={"protocol_whitelist": "file"})
        streams = tuple(self._container.streams.video)
        if not streams:
            raise ValueError("Video source has no video stream.")
        stream = streams[0]
        codec_name = str(getattr(stream.codec_context, "name", "")).lower()
        width = _positive_int(getattr(stream.codec_context, "width", None))
        height = _positive_int(getattr(stream.codec_context, "height", None))
        if codec_name not in self._allowed_codecs:
            raise ValueError("Video codec is not allowed.")
        if width is None or height is None or width * height > self._max_pixels:
            raise ValueError("Video dimensions exceed the configured pixel limit.")

        average_rate = _positive_fraction(getattr(stream, "average_rate", None))
        time_base = _positive_fraction(getattr(stream, "time_base", None))
        frame_count = _positive_int(getattr(stream, "frames", None))
        duration_ms = self._duration_ms(stream, time_base)
        format_name = str(getattr(self._container.format, "name", ""))
        self._probe = FileSourceProbe(
            path=path,
            size_bytes=stat.st_size,
            modified_ns=stat.st_mtime_ns,
            container_format=format_name,
            codec_name=codec_name,
            width=width,
            height=height,
            average_fps=float(average_rate) if average_rate is not None else None,
            time_base=time_base,
            declared_frame_count=frame_count,
            duration_ms=duration_ms,
        )
        self._frames = iter(self._container.decode(stream))

    def _duration_ms(self, stream: Any, time_base: Fraction | None) -> int | None:
        stream_duration = _positive_int(getattr(stream, "duration", None))
        if stream_duration is not None and time_base is not None:
            return round(float(stream_duration * time_base) * 1000)
        container_duration = _positive_int(getattr(self._container, "duration", None))
        if container_duration is not None:
            return round(container_duration / 1000)
        return None

    def _read_source(self) -> SourceFrame | None:
        if self._frames is None or self._camera_id is None:
            raise RuntimeError("Decoder is not initialized.")
        self._verify_unchanged()
        try:
            decoded = next(self._frames)
        except StopIteration:
            self._release_container()
            return None
        self._verify_unchanged()
        timestamp_ms = self._timestamp_ms(decoded)
        result = source_frame(
            camera_id=self._camera_id,
            source_frame_index=self._next_index,
            source_timestamp_ms=timestamp_ms,
            image=decoded.to_image(),
            max_pixels=self._max_pixels,
        )
        self._next_index += 1
        self._last_timestamp_ms = timestamp_ms
        return result

    def _timestamp_ms(self, frame: Any) -> int:
        pts = getattr(frame, "pts", None)
        time_base = _positive_fraction(getattr(frame, "time_base", None))
        if isinstance(pts, int) and not isinstance(pts, bool) and time_base is not None:
            current = pts * time_base
            if self._first_pts_seconds is None:
                self._first_pts_seconds = current
            timestamp_ms = round(float(current - self._first_pts_seconds) * 1000)
            if timestamp_ms < 0:
                raise ValueError("Video PTS precedes the timeline origin.")
            return timestamp_ms

        fps = self.probe.average_fps
        if fps is None or not math.isfinite(fps) or fps <= 0:
            raise ValueError("Video frame has no usable PTS or FPS fallback.")
        self._fallback_frames += 1
        predicted = round(self._next_index * 1000 / fps)
        return max(predicted, self._last_timestamp_ms or 0)

    def _verify_unchanged(self) -> None:
        if self._path is None or self._probe is None:
            raise RuntimeError("Video source path is unavailable.")
        stat = self._path.stat()
        if stat.st_size != self._probe.size_bytes or stat.st_mtime_ns != self._probe.modified_ns:
            raise ValueError("Video source changed while it was being decoded.")

    def _release_container(self) -> None:
        container, self._container = self._container, None
        self._frames = None
        if container is not None:
            container.close()

    def _close_source(self) -> None:
        self._release_container()
