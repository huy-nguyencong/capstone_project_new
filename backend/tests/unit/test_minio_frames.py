"""Unit tests for checksum-safe MinIO frame storage."""

from __future__ import annotations

import io
import uuid
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest
from PIL import Image

from person_search.storage.minio.frames import (
    FrameConflictError,
    FrameNotFoundError,
    InvalidFrameError,
    MinioFrameStore,
)

pytestmark = pytest.mark.unit


class MissingObject(Exception):
    code = "NoSuchKey"


class FakeResponse(io.BytesIO):
    def release_conn(self) -> None:
        pass


class FakeMinio:
    def __init__(self) -> None:
        self.objects: dict[str, tuple[bytes, str, dict[str, str]]] = {}

    def stat_object(self, bucket: str, key: str) -> SimpleNamespace:
        if key not in self.objects:
            raise MissingObject()
        data, content_type, metadata = self.objects[key]
        return SimpleNamespace(size=len(data), content_type=content_type, metadata=metadata)

    def put_object(self, bucket: str, key: str, stream: io.BytesIO, size: int, **kwargs) -> None:
        metadata = {f"x-amz-meta-{key}": value for key, value in kwargs["metadata"].items()}
        self.objects[key] = (stream.read(size), kwargs["content_type"], metadata)

    def get_object(self, bucket: str, key: str) -> FakeResponse:
        if key not in self.objects:
            raise MissingObject()
        return FakeResponse(self.objects[key][0])

    def remove_object(self, bucket: str, key: str) -> None:
        self.objects.pop(key, None)


def _jpeg(color: str = "red") -> bytes:
    stream = io.BytesIO()
    Image.new("RGB", (8, 6), color).save(stream, format="JPEG")
    return stream.getvalue()


def test_put_get_delete_is_idempotent_and_checksum_verified() -> None:
    client = FakeMinio()
    store = MinioFrameStore(client, "private")
    arguments = {
        "camera_id": uuid.uuid4(),
        "track_id": uuid.uuid4(),
        "captured_at": datetime.now(UTC),
        "data": _jpeg(),
        "content_type": "image/jpeg",
        "width": 8,
        "height": 6,
    }
    first = store.put_frame(**arguments)
    second = store.put_frame(**arguments)
    assert first == second
    assert store.get_frame(first.object_key) == arguments["data"]
    store.delete_frame(first.object_key)
    with pytest.raises(FrameNotFoundError):
        store.head_frame(first.object_key)


def test_existing_key_with_different_checksum_is_conflict() -> None:
    store = MinioFrameStore(FakeMinio(), "private")
    arguments = {
        "camera_id": uuid.uuid4(),
        "track_id": uuid.uuid4(),
        "captured_at": datetime.now(UTC),
        "content_type": "image/jpeg",
        "width": 8,
        "height": 6,
    }
    store.put_frame(data=_jpeg("red"), **arguments)
    with pytest.raises(FrameConflictError):
        store.put_frame(data=_jpeg("blue"), **arguments)


def test_mime_dimensions_and_corruption_are_rejected() -> None:
    store = MinioFrameStore(FakeMinio(), "private")
    common = {
        "camera_id": uuid.uuid4(),
        "track_id": uuid.uuid4(),
        "captured_at": datetime.now(UTC),
        "width": 8,
        "height": 6,
    }
    with pytest.raises(InvalidFrameError):
        store.put_frame(data=_jpeg(), content_type="image/png", **common)
    with pytest.raises(InvalidFrameError):
        store.put_frame(data=b"not-an-image", content_type="image/jpeg", **common)
