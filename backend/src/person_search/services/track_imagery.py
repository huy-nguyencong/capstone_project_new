from __future__ import annotations

import io
import logging
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol

from PIL import Image, ImageDraw, ImageEnhance, UnidentifiedImageError

from person_search.services.storage_status import StorageComponent, StorageMetrics
from person_search.storage.minio.frames import FrameNotFoundError, InvalidFrameError
from person_search.storage.postgres.models import (
    CameraStatus,
    PersonTrack,
    TrackIndexStatus,
    User,
    UserRole,
    UserStatus,
)
from person_search.storage.postgres.repositories import Repositories
from person_search.storage.postgres.unit_of_work import UnitOfWork

logger = logging.getLogger(__name__)

JPEG_MEDIA_TYPE = "image/jpeg"
PRIVATE_NO_STORE = "private, no-store"


class ImageVariant(StrEnum):
    PERSON_CROP = "PERSON_CROP"
    FULL_FRAME = "FULL_FRAME"


MIN_CROP_ASPECT = 0.2
MAX_CROP_ASPECT = 5.0


def parse_crop_aspect(raw: str | None) -> float | None:
    """Parse the optional ?aspect=<width/height> display hint for person crops."""

    if raw is None or raw == "":
        return None
    try:
        aspect = float(raw)
    except ValueError:
        raise ValueError("aspect must be a number.") from None
    if not MIN_CROP_ASPECT <= aspect <= MAX_CROP_ASPECT:
        raise ValueError(f"aspect must be between {MIN_CROP_ASPECT} and {MAX_CROP_ASPECT}.")
    return aspect


MARK_COLOR = (145, 132, 217)  # frontend --color-accent
MARK_DIM = 0.6


def parse_crop_mark(raw: str | None) -> bool:
    """Parse the optional ?mark=1 hint that outlines the matched person on the crop."""

    if raw is None or raw == "":
        return False
    if raw in {"1", "true"}:
        return True
    if raw in {"0", "false"}:
        return False
    raise ValueError("mark must be 0 or 1.")


def mark_person(image: Image.Image, person: tuple[int, int, int, int]) -> Image.Image:
    """Dim the surroundings and outline the matched person inside a widened crop."""

    left, top, right, bottom = person
    left, top = max(0, left), max(0, top)
    right, bottom = min(image.width, right), min(image.height, bottom)
    if right <= left or bottom <= top:
        return image
    marked = ImageEnhance.Brightness(image).enhance(MARK_DIM)
    marked.paste(image.crop((left, top, right, bottom)), (left, top))
    stroke = max(1, round(min(image.size) / 70))
    ImageDraw.Draw(marked).rectangle(
        (left, top, right - 1, bottom - 1), outline=MARK_COLOR, width=stroke
    )
    return marked


def fit_box_to_aspect(
    box: tuple[int, int, int, int], frame_size: tuple[int, int], aspect: float
) -> tuple[int, int, int, int]:
    """Grow a crop box to width/height == aspect using surrounding frame pixels.

    The box only ever grows (the person is never cut): a tall box keeps its height and gains
    width, a wide box keeps its width and gains height. The result stays centred on the person
    and is shifted inside the frame; near frame edges the aspect is matched as closely as the
    frame allows.
    """

    left, top, right, bottom = box
    frame_width, frame_height = frame_size
    width, height = right - left, bottom - top
    if width / height < aspect:
        target_width, target_height = round(height * aspect), height
    else:
        target_width, target_height = width, round(width / aspect)
    if target_width > frame_width:
        target_width = frame_width
        target_height = max(height, min(frame_height, round(frame_width / aspect)))
    if target_height > frame_height:
        target_height = frame_height
        target_width = max(width, min(frame_width, round(frame_height * aspect)))

    def place(start: int, size: int, target: int, limit: int) -> int:
        centred = start + (size - target) // 2
        return min(max(0, centred), limit - target)

    new_left = place(left, width, target_width, frame_width)
    new_top = place(top, height, target_height, frame_height)
    return new_left, new_top, new_left + target_width, new_top + target_height


class ImageAccessDeniedError(PermissionError):
    pass


class TrackImageNotFoundError(LookupError):
    pass


class TrackImageUnavailableError(RuntimeError):
    def __init__(self, track_id: uuid.UUID, reason: str) -> None:
        super().__init__(f"Track image is unavailable: {reason}.")
        self.track_id = track_id
        self.reason = reason


class FrameReader(Protocol):
    def get_frame(self, object_key: str) -> bytes: ...


@dataclass(frozen=True, slots=True)
class TrackImage:
    content: bytes
    width: int
    height: int
    media_type: str = JPEG_MEDIA_TYPE
    cache_control: str = PRIVATE_NO_STORE


@dataclass(frozen=True, slots=True)
class _FrameSource:
    track_id: uuid.UUID
    object_key: str
    bbox: tuple[int, int, int, int]
    frame_size: tuple[int, int]


class TrackImageService:
    def __init__(
        self,
        unit_of_work_factory: Callable[[], UnitOfWork],
        frames: FrameReader,
        *,
        max_edge: int = 1920,
        crop_padding_ratio: float = 0.0,
        jpeg_quality: int = 90,
        max_output_bytes: int = 5 * 1024 * 1024,
        storage_metrics: StorageMetrics | None = None,
    ) -> None:
        if max_edge < 16:
            raise ValueError("max_edge must be at least 16 pixels")
        if not 0.0 <= crop_padding_ratio <= 0.5:
            raise ValueError("crop_padding_ratio must be between 0 and 0.5")
        if not 30 <= jpeg_quality <= 95:
            raise ValueError("jpeg_quality must be between 30 and 95")
        self._unit_of_work_factory = unit_of_work_factory
        self._frames = frames
        self._max_edge = max_edge
        self._crop_padding_ratio = crop_padding_ratio
        self._jpeg_quality = jpeg_quality
        self._max_output_bytes = max_output_bytes
        self._storage_metrics = storage_metrics

    def search_result_image(
        self,
        actor_user_id: uuid.UUID,
        track_id: uuid.UUID,
        variant: ImageVariant,
        *,
        aspect: float | None = None,
        mark: bool = False,
    ) -> TrackImage:
        with self._unit_of_work_factory() as work:
            repositories = self._repositories(work)
            user = _active_user(repositories, actor_user_id)
            if user.role is not UserRole.OPERATOR or user.assigned_area_id is None:
                raise ImageAccessDeniedError("Only an Operator can open search result images.")
            rows = repositories.tracks.with_location([track_id])
            if not rows:
                raise TrackImageNotFoundError("Track image was not found.")
            track, camera, _ = rows[0]
            if (
                track.index_status is not TrackIndexStatus.READY
                or camera.area_id != user.assigned_area_id
                or camera.status is not CameraStatus.ACTIVE
            ):
                raise TrackImageNotFoundError("Track image was not found.")
            source = _source(track)
        return self._render(source, variant, aspect, mark)

    def case_result_image(
        self,
        actor_user_id: uuid.UUID,
        case_result_id: uuid.UUID,
        variant: ImageVariant,
        *,
        case_id: uuid.UUID | None = None,
        aspect: float | None = None,
        mark: bool = False,
    ) -> TrackImage:
        with self._unit_of_work_factory() as work:
            repositories = self._repositories(work)
            user = _active_user(repositories, actor_user_id)
            if user.role not in (UserRole.OPERATOR, UserRole.VIEWER):
                raise ImageAccessDeniedError("Only an Operator or Viewer can open Case images.")
            case_result = repositories.case_results.get(case_result_id)
            case = repositories.cases.get(case_result.case_id) if case_result else None
            if case_result is None or case is None:
                raise TrackImageNotFoundError("Case result was not found.")
            if case_id is not None and case.id != case_id:
                raise TrackImageNotFoundError("Case result was not found.")
            if user.role is UserRole.OPERATOR and case.owner_user_id != user.id:
                raise TrackImageNotFoundError("Case result was not found.")
            track = repositories.tracks.get(case_result.track_id)
            if track is None or not track.minio_object_key:
                raise TrackImageUnavailableError(case_result.track_id, "FRAME_MISSING")
            source = _source(track)
        return self._render(source, variant, aspect, mark)

    def _render(
        self,
        source: _FrameSource,
        variant: ImageVariant,
        aspect: float | None = None,
        mark: bool = False,
    ) -> TrackImage:
        try:
            data = self._frames.get_frame(source.object_key)
        except FrameNotFoundError as error:
            raise TrackImageUnavailableError(source.track_id, "FRAME_MISSING") from error
        except InvalidFrameError as error:
            raise TrackImageUnavailableError(source.track_id, "FRAME_CORRUPT") from error
        except Exception as error:
            if self._storage_metrics is not None:
                self._storage_metrics.record_error(StorageComponent.MINIO, error)
            raise
        try:
            with Image.open(io.BytesIO(data)) as opened:
                if opened.format not in {"JPEG", "PNG"}:
                    raise TrackImageUnavailableError(source.track_id, "FRAME_CORRUPT")
                if opened.size != source.frame_size:
                    raise TrackImageUnavailableError(source.track_id, "FRAME_CORRUPT")
                image = opened.convert("RGB")
        except (UnidentifiedImageError, OSError) as error:
            raise TrackImageUnavailableError(source.track_id, "FRAME_CORRUPT") from error

        box = self._clamped_box(source, image.size)
        if variant is ImageVariant.PERSON_CROP:
            if aspect is not None:
                box = fit_box_to_aspect(box, image.size, aspect)
            image = image.crop(box)
            if mark:
                x, y, width, height = source.bbox
                image = mark_person(
                    image, (x - box[0], y - box[1], x + width - box[0], y + height - box[1])
                )
        else:
            stroke = max(2, round(min(image.size) / 300))
            ImageDraw.Draw(image).rectangle(
                (box[0], box[1], box[2] - 1, box[3] - 1), outline=(255, 0, 0), width=stroke
            )
        image.thumbnail((self._max_edge, self._max_edge))
        content = self._encode(image, source.track_id)
        return TrackImage(content=content, width=image.width, height=image.height)

    def _clamped_box(
        self, source: _FrameSource, size: tuple[int, int]
    ) -> tuple[int, int, int, int]:
        x, y, width, height = source.bbox
        if width < 1 or height < 1:
            raise TrackImageUnavailableError(source.track_id, "BBOX_INVALID")
        pad_x = round(width * self._crop_padding_ratio)
        pad_y = round(height * self._crop_padding_ratio)
        left = max(0, x - pad_x)
        top = max(0, y - pad_y)
        right = min(size[0], x + width + pad_x)
        bottom = min(size[1], y + height + pad_y)
        if right <= left or bottom <= top:
            raise TrackImageUnavailableError(source.track_id, "BBOX_INVALID")
        return left, top, right, bottom

    def _encode(self, image: Image.Image, track_id: uuid.UUID) -> bytes:
        for quality in (self._jpeg_quality, 70, 50):
            stream = io.BytesIO()
            image.save(stream, format="JPEG", quality=quality)
            if stream.tell() <= self._max_output_bytes:
                return stream.getvalue()
        raise TrackImageUnavailableError(track_id, "RESPONSE_TOO_LARGE")

    @staticmethod
    def _repositories(work: UnitOfWork) -> Repositories:
        assert work.repositories is not None
        return work.repositories


def _active_user(repositories: Repositories, actor_user_id: uuid.UUID) -> User:
    user = repositories.users.get(actor_user_id)
    if user is None or user.status is not UserStatus.ACTIVE:
        raise ImageAccessDeniedError("Actor is not an active user.")
    return user


def _source(track: PersonTrack) -> _FrameSource:
    return _FrameSource(
        track_id=track.id,
        object_key=track.minio_object_key or "",
        bbox=(track.bbox_x, track.bbox_y, track.bbox_width, track.bbox_height),
        frame_size=(track.frame_width, track.frame_height),
    )
