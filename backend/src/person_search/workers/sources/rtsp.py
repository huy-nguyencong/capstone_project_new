"""Bounded RTSP frame source with SSRF policy, reconnects, and safe errors."""

from __future__ import annotations

import time
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any
from uuid import UUID

import av

from person_search.services.camera_runtime import CameraRuntime
from person_search.workers.contracts import SourceFrame, SourceKind
from person_search.workers.errors import AIErrorCode, AIWorkerError
from person_search.workers.sources.base import BaseFrameSource, source_frame
from person_search.workers.sources.file import DEFAULT_MAX_FRAME_PIXELS


class RtspFrameSource(BaseFrameSource):
    """Read a live RTSP stream while keeping credentials out of stored state and errors."""

    def __init__(
        self,
        *,
        encrypted_secret: str | None = None,
        access_resolver: Callable[[str, str | None], str] | None = None,
        opener: Callable[..., Any] = av.open,
        cancelled: Callable[[], bool] | None = None,
        connect_timeout: float = 8.0,
        read_timeout: float = 8.0,
        max_reconnects: int = 3,
        backoff_seconds: float = 0.25,
        max_backoff_seconds: float = 2.0,
        max_pixels: int = DEFAULT_MAX_FRAME_PIXELS,
        clock: Callable[[], float] = time.monotonic,
        sleeper: Callable[[float], None] = time.sleep,
    ) -> None:
        super().__init__(SourceKind.RTSP, cancelled=cancelled)
        if connect_timeout <= 0 or read_timeout <= 0:
            raise ValueError("RTSP timeouts must be positive.")
        if max_reconnects < 0 or backoff_seconds < 0 or max_backoff_seconds < 0:
            raise ValueError("RTSP reconnect settings must be nonnegative.")
        if max_pixels < 1:
            raise ValueError("max_pixels must be positive.")
        self._resolve_access = access_resolver
        if self._resolve_access is None:
            self._resolve_access = CameraRuntime.from_environment().connection_url
        self._encrypted_secret = encrypted_secret
        self._opener = opener
        self._connect_timeout = connect_timeout
        self._read_timeout = read_timeout
        self._max_reconnects = max_reconnects
        self._backoff_seconds = backoff_seconds
        self._max_backoff_seconds = max_backoff_seconds
        self._max_pixels = max_pixels
        self._clock = clock
        self._sleeper = sleeper
        self._public_url: str | None = None
        self._camera_id: UUID | None = None
        self._container: Any | None = None
        self._frames: Iterator[Any] | None = None
        self._timeline_origin: float | None = None
        self._next_index = 0
        self._last_capture_ms = 0
        self._reconnects = 0

    @property
    def reconnects(self) -> int:
        return self._reconnects

    def _open_source(self, source: str | Path, *, camera_id: UUID) -> None:
        if not isinstance(source, str):
            raise ValueError("RTSP source must be a credential-free URL string.")
        self._public_url = source
        self._camera_id = camera_id
        self._timeline_origin = self._clock()
        try:
            self._connect()
        except Exception as exc:
            raise self._connect_error(exc) from exc

    def _connect(self) -> None:
        if self._public_url is None:
            raise ValueError("RTSP URL is unavailable.")
        connection_url = self._resolve_access(self._public_url, self._encrypted_secret)
        container = None
        try:
            container = self._opener(
                connection_url,
                mode="r",
                options={
                    "protocol_whitelist": "tcp,tls,rtsp,rtsps",
                    "rtsp_transport": "tcp",
                    "rw_timeout": str(round(self._read_timeout * 1_000_000)),
                },
                timeout=(self._connect_timeout, self._read_timeout),
            )
            streams = tuple(container.streams.video)
            if not streams:
                raise ValueError("RTSP source has no video stream.")
            stream = streams[0]
            width = getattr(stream.codec_context, "width", 0)
            height = getattr(stream.codec_context, "height", 0)
            if (
                isinstance(width, bool)
                or isinstance(height, bool)
                or not isinstance(width, int)
                or not isinstance(height, int)
                or width < 1
                or height < 1
                or width * height > self._max_pixels
            ):
                raise ValueError("RTSP dimensions exceed the configured pixel limit.")
            self._container = container
            self._frames = iter(container.decode(stream))
        except Exception:
            if container is not None:
                container.close()
            raise
        finally:
            del connection_url

    def _read_source(self) -> SourceFrame | None:
        if self._camera_id is None or self._timeline_origin is None:
            raise RuntimeError("RTSP source is not initialized.")
        while True:
            if self._frames is None:
                raise RuntimeError("RTSP decoder is unavailable.")
            try:
                decoded = next(self._frames)
            except StopIteration as exc:
                self._reconnect(AIWorkerError(AIErrorCode.SOURCE_STREAM_ENDED, cause=exc))
                continue
            except Exception as exc:
                self._reconnect(self._read_error(exc))
                continue
            captured_ms = max(
                self._last_capture_ms,
                round((self._clock() - self._timeline_origin) * 1000),
            )
            frame = source_frame(
                camera_id=self._camera_id,
                source_frame_index=self._next_index,
                source_timestamp_ms=captured_ms,
                image=decoded.to_image(),
                max_pixels=self._max_pixels,
            )
            self._next_index += 1
            self._last_capture_ms = captured_ms
            return frame

    def _reconnect(self, error: AIWorkerError) -> None:
        last_error = error
        self._release_container()
        while self._reconnects < self._max_reconnects:
            self._reconnects += 1
            delay = min(
                self._max_backoff_seconds,
                self._backoff_seconds * (2 ** (self._reconnects - 1)),
            )
            self._interruptible_wait(delay)
            try:
                self._connect()
                return
            except Exception as exc:
                last_error = self._connect_error(exc)
                self._release_container()
        raise last_error

    def _interruptible_wait(self, delay: float) -> None:
        remaining = delay
        while remaining > 0:
            self._raise_if_cancelled()
            step = min(0.05, remaining)
            self._sleeper(step)
            remaining -= step
        self._raise_if_cancelled()

    @staticmethod
    def _connect_error(exc: Exception) -> AIWorkerError:
        if isinstance(exc, AIWorkerError):
            return exc
        if isinstance(exc, TimeoutError):
            return AIWorkerError(AIErrorCode.SOURCE_CONNECT_TIMEOUT, cause=exc)
        if isinstance(exc, PermissionError) or any(
            marker in str(exc).lower() for marker in ("401", "403", "unauthorized", "forbidden")
        ):
            return AIWorkerError(AIErrorCode.SOURCE_AUTH_FAILED, cause=exc)
        return AIWorkerError(AIErrorCode.SOURCE_OPEN_FAILED, cause=exc)

    @staticmethod
    def _read_error(exc: Exception) -> AIWorkerError:
        if isinstance(exc, TimeoutError):
            return AIWorkerError(AIErrorCode.SOURCE_READ_TIMEOUT, cause=exc)
        return AIWorkerError(AIErrorCode.SOURCE_READ_FAILED, cause=exc)

    def _release_container(self) -> None:
        container, self._container = self._container, None
        self._frames = None
        if container is not None:
            container.close()

    def _close_source(self) -> None:
        self._release_container()
