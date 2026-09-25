from __future__ import annotations

import hashlib
import io
import uuid
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest
from PIL import Image
from storage_fakes import FakeDatabase, FakeMinioClient, FakeUnitOfWork

from person_search.services.track_imagery import (
    ImageAccessDeniedError,
    ImageVariant,
    TrackImageNotFoundError,
    TrackImageService,
    TrackImageUnavailableError,
)
from person_search.storage.minio.frames import MinioFrameStore
from person_search.storage.postgres.models import (
    PersonTrack,
    TrackIndexStatus,
    UserRole,
    UserStatus,
)

pytestmark = pytest.mark.unit

NOW = datetime(2026, 9, 25, 8, 0, tzinfo=UTC)
WIDTH, HEIGHT = 64, 48


def _jpeg(size: tuple[int, int] = (WIDTH, HEIGHT)) -> bytes:
    stream = io.BytesIO()
    Image.new("RGB", size, (0, 160, 0)).save(stream, format="JPEG", quality=95)
    return stream.getvalue()


class World:
    def __init__(self, **service_options: object) -> None:
        self.database = database = FakeDatabase()
        self.minio = FakeMinioClient()
        self.area_a, self.area_b = uuid.uuid4(), uuid.uuid4()
        for area_id, name in ((self.area_a, "Area A"), (self.area_b, "Area B")):
            database.areas[area_id] = SimpleNamespace(id=area_id, name=name)
        self.camera_a, self.camera_b = uuid.uuid4(), uuid.uuid4()
        for camera_id, area_id in ((self.camera_a, self.area_a), (self.camera_b, self.area_b)):
            database.cameras[camera_id] = SimpleNamespace(
                id=camera_id, area_id=area_id, name="Camera"
            )
        self.operator = self.user(UserRole.OPERATOR, self.area_a)
        self.service = TrackImageService(
            lambda: FakeUnitOfWork(database),  # type: ignore[arg-type,return-value]
            MinioFrameStore(self.minio, "frames"),
            **service_options,  # type: ignore[arg-type]
        )

    def user(
        self,
        role: UserRole,
        area_id: uuid.UUID | None = None,
        status: UserStatus = UserStatus.ACTIVE,
    ) -> uuid.UUID:
        user_id = uuid.uuid4()
        self.database.users[user_id] = SimpleNamespace(
            id=user_id, role=role, status=status, assigned_area_id=area_id
        )
        return user_id

    def track(
        self,
        camera_id: uuid.UUID | None = None,
        *,
        bbox: tuple[int, int, int, int] = (8, 4, 20, 30),
        status: TrackIndexStatus = TrackIndexStatus.READY,
        frame: bytes | None = None,
        store_frame: bool = True,
    ) -> uuid.UUID:
        camera_id = camera_id or self.camera_a
        track_id = uuid.uuid4()
        key = f"tracks/v1/{camera_id}/2026/09/25/{track_id}/representative.jpg"
        data = frame if frame is not None else _jpeg()
        checksum = hashlib.sha256(data).hexdigest()
        if store_frame:
            self.minio.objects[key] = (data, "image/jpeg", {"sha256": checksum})
        self.database.tracks[track_id] = PersonTrack(
            id=track_id,
            camera_id=camera_id,
            processing_job_id=uuid.uuid4(),
            ai_config_version_id=uuid.uuid4(),
            appeared_at_utc=NOW,
            source_started_at_ms=0,
            source_ended_at_ms=1_000,
            representative_frame_timestamp_ms=500,
            bbox_x=bbox[0],
            bbox_y=bbox[1],
            bbox_width=bbox[2],
            bbox_height=bbox[3],
            frame_width=WIDTH,
            frame_height=HEIGHT,
            minio_object_key=key,
            frame_sha256=checksum,
            frame_size_bytes=len(data),
            encoder_version="rasa_cuhk_pedes_v1",
            vector_indexed_at=NOW if status is TrackIndexStatus.READY else None,
            index_status=status,
        )
        return track_id

    def case_result(self, owner_id: uuid.UUID, track_id: uuid.UUID) -> uuid.UUID:
        case_id, result_id = uuid.uuid4(), uuid.uuid4()
        self.database.cases[case_id] = SimpleNamespace(id=case_id, owner_user_id=owner_id)
        self.database.case_results[result_id] = SimpleNamespace(
            id=result_id, case_id=case_id, track_id=track_id
        )
        return result_id


def _decode(content: bytes) -> Image.Image:
    image = Image.open(io.BytesIO(content))
    assert image.format == "JPEG"
    return image.convert("RGB")


def test_person_crop_is_rendered_from_bbox_without_persisting() -> None:
    world = World()
    track_id = world.track()

    image = world.service.search_result_image(world.operator, track_id, ImageVariant.PERSON_CROP)

    assert (image.width, image.height) == (20, 30)
    assert image.media_type == "image/jpeg"
    assert image.cache_control == "private, no-store"
    assert _decode(image.content).size == (20, 30)
    assert world.minio.puts == 0
    assert len(world.minio.objects) == 1


def test_full_frame_preview_draws_bbox_outline() -> None:
    world = World()
    track_id = world.track()

    image = world.service.search_result_image(world.operator, track_id, ImageVariant.FULL_FRAME)

    decoded = _decode(image.content)
    assert decoded.size == (WIDTH, HEIGHT)
    red, green, _ = decoded.getpixel((8, 15))
    assert red > 150 and green < 100
    red, green, _ = decoded.getpixel((50, 40))
    assert red < 80 and green > 120


def test_bbox_on_frame_edge_with_padding_is_clamped() -> None:
    world = World(crop_padding_ratio=0.5)
    track_id = world.track(bbox=(44, 18, 20, 30))

    image = world.service.search_result_image(world.operator, track_id, ImageVariant.PERSON_CROP)

    assert (image.width, image.height) == (WIDTH - 34, HEIGHT - 3)


def test_bbox_outside_decoded_frame_is_reported() -> None:
    world = World()
    track_id = world.track(bbox=(70, 4, 5, 5))

    with pytest.raises(TrackImageUnavailableError) as error:
        world.service.search_result_image(world.operator, track_id, ImageVariant.PERSON_CROP)

    assert error.value.reason == "BBOX_INVALID"


def test_large_frame_is_downscaled_to_max_edge() -> None:
    world = World(max_edge=32)
    track_id = world.track()

    image = world.service.search_result_image(world.operator, track_id, ImageVariant.FULL_FRAME)

    assert (image.width, image.height) == (32, 24)


def test_response_size_limit_is_enforced() -> None:
    world = World(max_output_bytes=10)
    track_id = world.track()

    with pytest.raises(TrackImageUnavailableError) as error:
        world.service.search_result_image(world.operator, track_id, ImageVariant.FULL_FRAME)

    assert error.value.reason == "RESPONSE_TOO_LARGE"


@pytest.mark.parametrize(
    ("setup", "reason"),
    [
        ("missing", "FRAME_MISSING"),
        ("checksum", "FRAME_CORRUPT"),
        ("dimensions", "FRAME_CORRUPT"),
        ("garbage", "FRAME_CORRUPT"),
    ],
)
def test_missing_or_corrupt_frame_is_reported(setup: str, reason: str) -> None:
    world = World()
    if setup == "missing":
        track_id = world.track(store_frame=False)
    elif setup == "dimensions":
        track_id = world.track(frame=_jpeg((32, 32)))
    elif setup == "garbage":
        track_id = world.track(frame=b"\xff\xd8not-an-image\xff\xd9")
    else:
        track_id = world.track()
        key = world.database.tracks[track_id].minio_object_key
        assert key is not None
        _, content_type, metadata = world.minio.objects[key]
        world.minio.objects[key] = (_jpeg((WIDTH, HEIGHT - 1)), content_type, metadata)

    with pytest.raises(TrackImageUnavailableError) as error:
        world.service.search_result_image(world.operator, track_id, ImageVariant.PERSON_CROP)

    assert error.value.reason == reason
    assert error.value.track_id == track_id


def test_search_image_outside_operator_area_is_not_found() -> None:
    world = World()
    foreign = world.track(world.camera_b)

    with pytest.raises(TrackImageNotFoundError):
        world.service.search_result_image(world.operator, foreign, ImageVariant.PERSON_CROP)


def test_search_image_of_unready_or_unknown_track_is_not_found() -> None:
    world = World()
    pending = world.track(status=TrackIndexStatus.PENDING)

    for track_id in (pending, uuid.uuid4()):
        with pytest.raises(TrackImageNotFoundError):
            world.service.search_result_image(world.operator, track_id, ImageVariant.FULL_FRAME)


@pytest.mark.parametrize(
    ("role", "status"),
    [
        (UserRole.VIEWER, UserStatus.ACTIVE),
        (UserRole.ADMIN, UserStatus.ACTIVE),
        (UserRole.OPERATOR, UserStatus.LOCKED),
    ],
)
def test_search_image_requires_active_operator(role: UserRole, status: UserStatus) -> None:
    world = World()
    actor = world.user(role, world.area_a if role is UserRole.OPERATOR else None, status)
    track_id = world.track()

    with pytest.raises(ImageAccessDeniedError):
        world.service.search_result_image(actor, track_id, ImageVariant.PERSON_CROP)


def test_operator_keeps_case_images_after_area_reassignment() -> None:
    world = World()
    track_id = world.track(world.camera_a)
    result_id = world.case_result(world.operator, track_id)
    world.database.users[world.operator].assigned_area_id = world.area_b

    image = world.service.case_result_image(world.operator, result_id, ImageVariant.PERSON_CROP)

    assert (image.width, image.height) == (20, 30)
    with pytest.raises(TrackImageNotFoundError):
        world.service.search_result_image(world.operator, track_id, ImageVariant.PERSON_CROP)


def test_operator_cannot_open_other_operators_case_image() -> None:
    world = World()
    other = world.user(UserRole.OPERATOR, world.area_a)
    result_id = world.case_result(other, world.track())

    with pytest.raises(TrackImageNotFoundError):
        world.service.case_result_image(world.operator, result_id, ImageVariant.FULL_FRAME)


def test_viewer_can_open_any_case_image() -> None:
    world = World()
    viewer = world.user(UserRole.VIEWER)
    result_id = world.case_result(world.operator, world.track(world.camera_b))

    image = world.service.case_result_image(viewer, result_id, ImageVariant.FULL_FRAME)

    assert (image.width, image.height) == (WIDTH, HEIGHT)


def test_admin_cannot_open_case_image_and_unknown_result_is_not_found() -> None:
    world = World()
    admin = world.user(UserRole.ADMIN)
    viewer = world.user(UserRole.VIEWER)
    result_id = world.case_result(world.operator, world.track())

    with pytest.raises(ImageAccessDeniedError):
        world.service.case_result_image(admin, result_id, ImageVariant.PERSON_CROP)
    with pytest.raises(TrackImageNotFoundError):
        world.service.case_result_image(viewer, uuid.uuid4(), ImageVariant.PERSON_CROP)


def test_case_image_with_missing_frame_reports_unavailable() -> None:
    world = World()
    viewer = world.user(UserRole.VIEWER)
    track_id = world.track(store_frame=False)
    result_id = world.case_result(world.operator, track_id)

    with pytest.raises(TrackImageUnavailableError) as error:
        world.service.case_result_image(viewer, result_id, ImageVariant.PERSON_CROP)

    assert error.value.reason == "FRAME_MISSING"
    assert result_id in world.database.case_results
