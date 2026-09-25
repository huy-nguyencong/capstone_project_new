"""Real-service integration tests for STO-09 and STO-10."""

from __future__ import annotations

import io
import os
import urllib.error
import urllib.request
import uuid
from datetime import UTC, datetime

import pytest
from dotenv import load_dotenv
from PIL import Image

from person_search.config import MilvusSettings, MinioSettings
from person_search.storage.milvus.client import MilvusStorage
from person_search.storage.milvus.vectors import MilvusPersonTrackIndex, VectorFilter
from person_search.storage.minio.client import MinioStorage
from person_search.storage.minio.frames import MinioFrameStore

load_dotenv()
pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        os.getenv("PERSON_SEARCH_RUN_ADAPTER_INTEGRATION") != "1",
        reason="set adapter integration flag with the local storage stack",
    ),
]


def _jpeg() -> bytes:
    stream = io.BytesIO()
    Image.new("RGB", (16, 12), "green").save(stream, format="JPEG")
    return stream.getvalue()


def test_minio_frame_round_trip_and_private_bucket() -> None:
    settings = MinioSettings.from_environment(os.environ)
    storage = MinioStorage(settings)
    store = MinioFrameStore(storage.client, settings.bucket)
    info = store.put_frame(
        camera_id=uuid.uuid4(),
        track_id=uuid.uuid4(),
        captured_at=datetime.now(UTC),
        data=_jpeg(),
        content_type="image/jpeg",
        width=16,
        height=12,
    )
    try:
        assert store.get_frame(info.object_key) == _jpeg()
        assert store.head_frame(info.object_key).checksum_sha256 == info.checksum_sha256
        scheme = "https" if settings.secure else "http"
        with pytest.raises(urllib.error.HTTPError) as error:
            urllib.request.urlopen(
                f"{scheme}://{settings.endpoint}/{settings.bucket}/{info.object_key}",
                timeout=settings.timeout_seconds,
            )
        assert error.value.code in {401, 403}
    finally:
        store.delete_frame(info.object_key)
        storage.close()


def test_milvus_upsert_filtered_search_get_and_delete() -> None:
    settings = MilvusSettings.from_environment(os.environ)
    storage = MilvusStorage(settings)
    suffix = uuid.uuid4().hex[:8]
    index = MilvusPersonTrackIndex(
        storage.client,
        encoder_version=f"integration_{suffix}",
        dimension=4,
        timeout=settings.timeout_seconds,
        alias=f"person_track_test_{suffix}",
    )
    area_a, area_b, camera = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    track_a, track_b = uuid.uuid4(), uuid.uuid4()
    try:
        index.ensure_collection()
        index.ensure_collection()
        index.upsert(
            track_id=track_a,
            vector=[1.0, 0.0, 0.0, 0.0],
            area_id=area_a,
            camera_id=camera,
            appeared_at=datetime.now(UTC),
        )
        index.upsert(
            track_id=track_b,
            vector=[1.0, 0.0, 0.0, 0.0],
            area_id=area_b,
            camera_id=camera,
            appeared_at=datetime.now(UTC),
        )
        storage.client.flush(index.collection_name)
        hits = index.search([1.0, 0.0, 0.0, 0.0], VectorFilter(area_id=area_a), top_k=4)
        assert [hit.track_id for hit in hits] == [track_a]
        assert index.get(track_a) is not None
        index.delete(track_a)
        storage.client.flush(index.collection_name)
        assert index.get(track_a) is None
    finally:
        if storage.client.has_collection(index.collection_name):
            alias_response = storage.client.list_aliases(index.collection_name)
            aliases = alias_response.get("aliases", [])
            if index.alias in aliases:
                storage.client.drop_alias(index.alias)
            storage.client.drop_collection(index.collection_name)
        storage.close()
