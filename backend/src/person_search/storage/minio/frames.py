"""Private, checksum-safe full-frame object adapter."""

from __future__ import annotations

import hashlib
import io
import uuid
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from PIL import Image, UnidentifiedImageError

from person_search.storage.contracts import FRAME_OBJECT_PREFIX

SUPPORTED_MEDIA_TYPES = {"image/jpeg": "JPEG", "image/png": "PNG"}


class FrameNotFoundError(FileNotFoundError):
    pass


class FrameConflictError(RuntimeError):
    pass


class InvalidFrameError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class FrameInfo:
    object_key: str
    checksum_sha256: str
    size_bytes: int
    content_type: str


def frame_object_key(
    camera_id: uuid.UUID,
    captured_at: datetime,
    track_id: uuid.UUID,
    extension: str = "jpg",
) -> str:
    if captured_at.tzinfo is None:
        raise ValueError("captured_at must be timezone-aware")
    return (
        f"{FRAME_OBJECT_PREFIX}/{camera_id}/{captured_at:%Y/%m/%d}/{track_id}/"
        f"representative.{extension}"
    )


class MinioFrameStore:
    def __init__(self, client: Any, bucket: str, *, max_bytes: int = 20 * 1024 * 1024) -> None:
        self.client = client
        self.bucket = bucket
        self.max_bytes = max_bytes

    @staticmethod
    def _is_missing(error: Exception) -> bool:
        return getattr(error, "code", None) in {"NoSuchKey", "NoSuchObject", "NotFound"}

    def _validate(
        self, data: bytes, content_type: str, expected_width: int, expected_height: int
    ) -> str:
        if content_type not in SUPPORTED_MEDIA_TYPES:
            raise InvalidFrameError("Only JPEG and PNG frames are supported.")
        if not data or len(data) > self.max_bytes:
            raise InvalidFrameError("Frame size is outside the accepted range.")
        try:
            with Image.open(io.BytesIO(data)) as image:
                if image.format != SUPPORTED_MEDIA_TYPES[content_type]:
                    raise InvalidFrameError("Declared MIME type does not match image bytes.")
                if image.size != (expected_width, expected_height):
                    raise InvalidFrameError("Image dimensions do not match frame metadata.")
                image.verify()
        except (UnidentifiedImageError, OSError) as error:
            raise InvalidFrameError("Frame bytes are not a valid supported image.") from error
        return hashlib.sha256(data).hexdigest()

    def head_frame(self, object_key: str) -> FrameInfo:
        try:
            stat = self.client.stat_object(self.bucket, object_key)
        except Exception as error:
            if self._is_missing(error):
                raise FrameNotFoundError(object_key) from error
            raise
        metadata = {key.lower(): value for key, value in (stat.metadata or {}).items()}
        checksum = metadata.get("x-amz-meta-sha256") or metadata.get("sha256")
        if not checksum:
            raise InvalidFrameError("Stored object is missing its checksum metadata.")
        return FrameInfo(object_key, checksum, stat.size, stat.content_type)

    def put_frame(
        self,
        *,
        camera_id: uuid.UUID,
        track_id: uuid.UUID,
        captured_at: datetime,
        data: bytes,
        content_type: str,
        width: int,
        height: int,
    ) -> FrameInfo:
        checksum = self._validate(data, content_type, width, height)
        extension = "jpg" if content_type == "image/jpeg" else "png"
        object_key = frame_object_key(camera_id, captured_at, track_id, extension)
        try:
            existing = self.head_frame(object_key)
        except FrameNotFoundError:
            existing = None
        if existing is not None:
            if existing.checksum_sha256 != checksum:
                raise FrameConflictError("Object key already exists with a different checksum.")
            return existing
        self.client.put_object(
            self.bucket,
            object_key,
            io.BytesIO(data),
            len(data),
            content_type=content_type,
            metadata={"track-id": str(track_id), "sha256": checksum},
        )
        return FrameInfo(object_key, checksum, len(data), content_type)

    def get_frame(self, object_key: str) -> bytes:
        expected = self.head_frame(object_key)
        try:
            response = self.client.get_object(self.bucket, object_key)
        except Exception as error:
            if self._is_missing(error):
                raise FrameNotFoundError(object_key) from error
            raise
        try:
            data = response.read()
        finally:
            response.close()
            response.release_conn()
        if hashlib.sha256(data).hexdigest() != expected.checksum_sha256:
            raise InvalidFrameError("Stored frame checksum verification failed.")
        return data

    def list_frame_keys(self, prefix: str = FRAME_OBJECT_PREFIX) -> Iterator[str]:
        for item in self.client.list_objects(self.bucket, prefix=f"{prefix}/", recursive=True):
            yield item.object_name

    def delete_frame(self, object_key: str) -> None:
        self.client.remove_object(self.bucket, object_key)
