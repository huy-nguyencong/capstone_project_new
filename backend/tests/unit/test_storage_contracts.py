"""Contract tests for the decisions accepted in ADR-0001."""

from dataclasses import replace
from datetime import UTC, datetime, timedelta, timezone
from uuid import UUID, uuid4

import pytest

from person_search.storage.contracts import (
    APPLICATION_FRAME_BUCKET,
    MILVUS_ACTIVE_ALIAS,
    RASA_EMBEDDING_DIMENSION,
    RASA_ENCODER_VERSION,
    BoundingBoxPixels,
    EncoderManifest,
    TrackIngestionRequest,
    TrackStorageState,
    VectorMetric,
    can_transition_track_state,
    frame_object_key,
    milvus_collection_name,
)

pytestmark = pytest.mark.unit


def encoder_manifest() -> EncoderManifest:
    return EncoderManifest(
        version=RASA_ENCODER_VERSION,
        embedding_dimension=RASA_EMBEDDING_DIMENSION,
        checkpoint_sha256="ab" * 32,
    )


def normalized_embedding() -> tuple[float, ...]:
    return (1.0,) + (0.0,) * (RASA_EMBEDDING_DIMENSION - 1)


def valid_request() -> TrackIngestionRequest:
    return TrackIngestionRequest(
        track_id=uuid4(),
        camera_id=uuid4(),
        area_id=uuid4(),
        processing_job_id=uuid4(),
        ai_config_version_id=uuid4(),
        timeline_origin_utc=datetime(2026, 9, 25, 1, 2, 3, tzinfo=UTC),
        source_frame_index=300,
        source_started_at_ms=10_000,
        representative_frame_timestamp_ms=11_000,
        source_ended_at_ms=12_000,
        bbox=BoundingBoxPixels(
            x=100,
            y=40,
            width=80,
            height=210,
            frame_width=1920,
            frame_height=1080,
        ),
        frame_bytes=b"\xff\xd8representative-jpeg-bytes\xff\xd9",
        embedding=normalized_embedding(),
        encoder=encoder_manifest(),
    )


def test_storage_names_are_stable() -> None:
    assert APPLICATION_FRAME_BUCKET == "person-search-frames"
    assert MILVUS_ACTIVE_ALIAS == "person_track_embeddings_active"
    assert (
        milvus_collection_name(RASA_ENCODER_VERSION)
        == "person_track_embeddings_rasa_cuhk_pedes_v1"
    )


def test_frame_object_key_is_deterministic_and_date_partitioned() -> None:
    camera_id = UUID("a515508c-7f20-4e76-b973-7a1fe72b4076")
    track_id = UUID("a6ed481c-1208-41b7-bb36-a768450c38e9")
    appeared_at = datetime(2026, 9, 25, 14, 30, tzinfo=UTC)

    assert frame_object_key(camera_id, appeared_at, track_id) == (
        "tracks/v1/a515508c-7f20-4e76-b973-7a1fe72b4076/2026/09/25/"
        "a6ed481c-1208-41b7-bb36-a768450c38e9/representative.jpg"
    )


@pytest.mark.parametrize(
    ("current", "target", "expected"),
    [
        (TrackStorageState.PENDING, TrackStorageState.READY, True),
        (TrackStorageState.PENDING, TrackStorageState.FAILED, True),
        (TrackStorageState.FAILED, TrackStorageState.PENDING, True),
        (TrackStorageState.READY, TrackStorageState.FAILED, False),
        (TrackStorageState.READY, TrackStorageState.PENDING, False),
    ],
)
def test_track_state_transitions(
    current: TrackStorageState,
    target: TrackStorageState,
    expected: bool,
) -> None:
    assert can_transition_track_state(current, target) is expected


def test_bbox_uses_original_frame_pixels() -> None:
    bbox = BoundingBoxPixels(
        x=0,
        y=0,
        width=1920,
        height=1080,
        frame_width=1920,
        frame_height=1080,
    )

    assert bbox.x + bbox.width == bbox.frame_width
    assert bbox.y + bbox.height == bbox.frame_height


@pytest.mark.parametrize(
    "values",
    [
        {"x": -1},
        {"y": -1},
        {"width": 0},
        {"height": 0},
        {"x": 1910, "width": 11},
        {"y": 1070, "height": 11},
        {"frame_width": 0},
        {"frame_height": 0},
    ],
)
def test_bbox_rejects_invalid_coordinates(values: dict[str, int]) -> None:
    defaults = {
        "x": 100,
        "y": 40,
        "width": 80,
        "height": 210,
        "frame_width": 1920,
        "frame_height": 1080,
    }

    with pytest.raises(ValueError):
        BoundingBoxPixels(**(defaults | values))


def test_encoder_manifest_locks_rasa_vector_space() -> None:
    manifest = encoder_manifest()

    assert manifest.embedding_dimension == 256
    assert manifest.metric is VectorMetric.INNER_PRODUCT
    assert manifest.l2_normalized is True


@pytest.mark.parametrize(
    "changes",
    [
        {"embedding_dimension": 768},
        {"embedding_dimension": 256.0},
        {"embedding_dimension": 0, "version": "custom_encoder_v1"},
        {"checkpoint_sha256": "not-a-sha256"},
        {"metric": "COSINE"},
        {"l2_normalized": False},
        {"l2_normalized": "true"},
    ],
)
def test_encoder_manifest_rejects_incompatible_rasa_profile(changes: dict[str, object]) -> None:
    values: dict[str, object] = {
        "version": RASA_ENCODER_VERSION,
        "embedding_dimension": RASA_EMBEDDING_DIMENSION,
        "checkpoint_sha256": "ab" * 32,
    }
    values.update(changes)

    with pytest.raises((TypeError, ValueError)):
        EncoderManifest(**values)  # type: ignore[arg-type]


def test_ingestion_request_derives_time_and_frame_hash() -> None:
    request = valid_request()

    assert request.appeared_at_utc == datetime(2026, 9, 25, 1, 2, 13, tzinfo=UTC)
    assert len(request.frame_sha256) == 64
    assert isinstance(request.embedding, tuple)


def test_ingestion_request_rejects_non_uuid4_identifier() -> None:
    request = valid_request()

    with pytest.raises(ValueError, match="UUIDv4"):
        replace(request, track_id=UUID(int=0))


def test_ingestion_request_rejects_non_utc_timeline() -> None:
    request = valid_request()
    non_utc = datetime(2026, 9, 25, 8, 2, 3, tzinfo=timezone(timedelta(hours=7)))

    with pytest.raises(ValueError, match="normalized to UTC"):
        replace(request, timeline_origin_utc=non_utc)

    with pytest.raises(ValueError, match="normalized to UTC"):
        replace(request, timeline_origin_utc="2026-09-25T01:02:03Z")  # type: ignore[arg-type]


@pytest.mark.parametrize(
    "changes",
    [
        {"source_started_at_ms": -1},
        {"source_ended_at_ms": 9_000},
        {"representative_frame_timestamp_ms": 13_000},
        {"source_frame_index": -1},
        {"source_frame_index": True},
    ],
)
def test_ingestion_request_rejects_invalid_source_timeline(
    changes: dict[str, int],
) -> None:
    with pytest.raises(ValueError):
        replace(valid_request(), **changes)


def test_ingestion_request_rejects_wrong_embedding_dimension() -> None:
    with pytest.raises(ValueError, match="length"):
        replace(valid_request(), embedding=(1.0, 0.0))


def test_ingestion_request_rejects_invalid_contract_objects() -> None:
    request = valid_request()

    with pytest.raises(ValueError, match="bbox"):
        replace(request, bbox={})  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="encoder"):
        replace(request, encoder={})  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="non-empty JPEG"):
        replace(request, frame_bytes=b"")
    with pytest.raises(ValueError, match="numeric sequence"):
        replace(request, embedding="not-a-vector")


def test_ingestion_request_rejects_non_finite_embedding() -> None:
    values = list(normalized_embedding())
    values[1] = float("nan")

    with pytest.raises(ValueError, match="finite"):
        replace(valid_request(), embedding=values)


def test_ingestion_request_rejects_non_normalized_embedding() -> None:
    with pytest.raises(ValueError, match="L2-normalized"):
        replace(valid_request(), embedding=(0.5,) + (0.0,) * 255)


def test_ingestion_request_only_accepts_jpeg_full_frames() -> None:
    with pytest.raises(ValueError, match="image/jpeg"):
        replace(valid_request(), frame_media_type="image/png")

    with pytest.raises(ValueError, match="complete JPEG"):
        replace(valid_request(), frame_bytes=b"not-really-a-jpeg")


@pytest.mark.parametrize("version", ["RaSa-v1", "../rasa", "ra", "rasa.v1"])
def test_collection_name_rejects_unsafe_encoder_versions(version: str) -> None:
    with pytest.raises(ValueError):
        milvus_collection_name(version)
