"""Phase 5 search orchestration and replaceable encoder gateway."""

from __future__ import annotations

import base64
import io
import json
import math
import os
import uuid
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Protocol
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from PIL import Image, UnidentifiedImageError

from person_search.services.track_search import (
    TrackSearchQuery,
    TrackSearchResult,
    TrackSearchService,
)
from person_search.storage.milvus.vectors import MilvusPersonTrackIndex
from person_search.storage.postgres.models import CameraStatus, UserRole, UserStatus
from person_search.storage.postgres.repositories import ActorContext, Repositories
from person_search.storage.postgres.unit_of_work import UnitOfWork

MAX_QUERY_IMAGE_BYTES = 10 * 1024 * 1024
MAX_QUERY_IMAGE_PIXELS = 24_000_000
DEMO_ENCODER_VERSION = "fake_demo_v1"
class EncoderUnavailableError(RuntimeError):
    pass


class InvalidQueryImageError(ValueError):
    pass


class EncoderGateway(Protocol):
    def image(self, content: bytes, *, version: str, dimension: int) -> Sequence[float]: ...
    def text(self, text: str, *, version: str, dimension: int) -> Sequence[float]: ...


@dataclass(frozen=True, slots=True)
class SearchResponse:
    mode: str
    prompt: str | None
    encoder_version: str
    top_k: int
    results: tuple[TrackSearchResult, ...]


@dataclass(frozen=True, slots=True)
class OperatorCamera:
    id: uuid.UUID
    code: str
    name: str
    ai_enabled: bool


class HttpEncoderGateway:
    """JSON-over-HTTP gateway for a production multimodal encoder service."""

    def __init__(self, base_url: str, *, timeout: float = 10.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def image(self, content: bytes, *, version: str, dimension: int) -> Sequence[float]:
        decode_query_image(content)
        return self._post(
            "/encode/image",
            {"image_base64": base64.b64encode(content).decode("ascii"), "encoder_version": version},
            version,
            dimension,
        )

    def text(self, text: str, *, version: str, dimension: int) -> Sequence[float]:
        return self._post(
            "/encode/text", {"text": text, "encoder_version": version}, version, dimension
        )

    def _post(
        self, path: str, payload: Mapping[str, object], version: str, dimension: int
    ) -> Sequence[float]:
        request = Request(
            self.base_url + path,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json", "Accept": "application/json"},
            method="POST",
        )
        try:
            with urlopen(request, timeout=self.timeout) as response:  # noqa: S310
                body = json.load(response)
        except (HTTPError, URLError, TimeoutError, OSError, ValueError) as error:
            raise EncoderUnavailableError("Encoder service is unavailable.") from error
        if body.get("encoder_version") != version:
            raise EncoderUnavailableError("Encoder returned a different model version.")
        embedding = body.get("embedding")
        if not isinstance(embedding, list) or len(embedding) != dimension:
            raise EncoderUnavailableError("Encoder returned an invalid embedding.")
        try:
            values = [float(value) for value in embedding]
        except (TypeError, ValueError) as error:
            raise EncoderUnavailableError("Encoder returned an invalid embedding.") from error
        if not all(math.isfinite(value) for value in values):
            raise EncoderUnavailableError("Encoder returned an invalid embedding.")
        norm = math.sqrt(sum(value * value for value in values))
        if not math.isclose(norm, 1.0, abs_tol=1e-3):
            raise EncoderUnavailableError("Encoder returned an unnormalized embedding.")
        return values


class SearchService:
    def __init__(
        self,
        unit_of_work_factory: Callable[[], UnitOfWork],
        milvus_client: object,
        *,
        encoder: EncoderGateway | None = None,
        allow_demo: bool = False,
    ) -> None:
        self._unit_of_work_factory = unit_of_work_factory
        self._milvus_client = milvus_client
        self._encoder = encoder
        self._allow_demo = allow_demo

    def cameras(self, actor_user_id: uuid.UUID) -> tuple[OperatorCamera, ...]:
        with self._unit_of_work_factory() as work:
            repositories = _repositories(work)
            user = repositories.users.get(actor_user_id)
            if (
                user is None
                or user.status is not UserStatus.ACTIVE
                or user.role is not UserRole.OPERATOR
                or user.assigned_area_id is None
            ):
                return ()
            rows = repositories.cameras.page_for_actor(
                ActorContext(user.id, user.role, user.assigned_area_id), limit=100
            )
            return tuple(
                OperatorCamera(camera.id, camera.code, camera.name, camera.ai_enabled)
                for camera in rows
                if camera.status is CameraStatus.ACTIVE
            )

    def search_image(self, actor: uuid.UUID, content: bytes, **filters: object) -> SearchResponse:
        decode_query_image(content)
        config = self.active_config()
        vector = self.gateway(config.encoder_version).image(
            content, version=config.encoder_version, dimension=config.encoder_dimension
        )
        return self._search(actor, "IMAGE", None, vector, config, filters)

    def search_text(self, actor: uuid.UUID, text: str, **filters: object) -> SearchResponse:
        config = self.active_config()
        vector = self.gateway(config.encoder_version).text(
            text, version=config.encoder_version, dimension=config.encoder_dimension
        )
        return self._search(actor, "TEXT", text, vector, config, filters)

    def search_attributes(
        self, actor: uuid.UUID, attributes: Mapping[str, object], **filters: object
    ) -> SearchResponse:
        prompt = attributes_prompt(attributes)
        config = self.active_config()
        vector = self.gateway(config.encoder_version).text(
            prompt, version=config.encoder_version, dimension=config.encoder_dimension
        )
        return self._search(actor, "ATTRIBUTES", prompt, vector, config, filters)

    def _search(self, actor, mode, prompt, vector, config, filters) -> SearchResponse:
        alias = (
            "person_track_embeddings_demo"
            if config.encoder_version == DEMO_ENCODER_VERSION
            else "person_track_embeddings_active"
        )
        vectors = MilvusPersonTrackIndex(
            self._milvus_client,
            encoder_version=config.encoder_version,
            dimension=config.encoder_dimension,
            alias=alias,
        )
        service = TrackSearchService(self._unit_of_work_factory, vectors)
        query = TrackSearchQuery(embedding=vector, **filters)
        results = service.search(actor, query)
        return SearchResponse(mode, prompt, config.encoder_version, query.top_k, tuple(results))

    def active_config(self):
        with self._unit_of_work_factory() as work:
            config = _repositories(work).ai_configs.active()
            if config is None:
                raise EncoderUnavailableError("No active encoder configuration exists.")
            return config

    def gateway(self, version: str) -> EncoderGateway:
        if self._encoder is not None:
            return self._encoder
        if version == DEMO_ENCODER_VERSION:
            if not self._allow_demo:
                raise EncoderUnavailableError("Demo encoder is not enabled.")
            from person_search.demo import DemoEncoderGateway

            return DemoEncoderGateway()
        url = os.environ.get("PERSON_SEARCH_ENCODER_URL", "").strip()
        if not url:
            raise EncoderUnavailableError("Encoder service is not configured.")
        return HttpEncoderGateway(url)


def decode_query_image(content: bytes) -> Image.Image:
    if not content or len(content) > MAX_QUERY_IMAGE_BYTES:
        raise InvalidQueryImageError("Image is empty or too large.")
    try:
        with Image.open(io.BytesIO(content)) as opened:
            if opened.format not in {"JPEG", "PNG"}:
                raise InvalidQueryImageError("Only JPEG and PNG images are supported.")
            if opened.width * opened.height > MAX_QUERY_IMAGE_PIXELS:
                raise InvalidQueryImageError("Image dimensions are too large.")
            opened.load()
            return opened.convert("RGB")
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as error:
        raise InvalidQueryImageError("Image is invalid.") from error


def attributes_prompt(attributes: Mapping[str, object]) -> str:
    allowed = {"upper_color", "lower_color", "upper_type", "has_backpack"}
    if not attributes or set(attributes) - allowed:
        raise ValueError("Attributes contain unsupported fields.")
    colors = {"red", "blue", "white", "black", "green", "yellow", "gray", "beige"}
    clothing = {
        "t_shirt": "t-shirt",
        "shirt": "shirt",
        "jacket": "jacket",
        "dress": "dress",
    }
    upper_color = attributes.get("upper_color")
    lower_color = attributes.get("lower_color")
    upper_type = attributes.get("upper_type")
    backpack = attributes.get("has_backpack")
    if upper_color is not None and upper_color not in colors:
        raise ValueError("upper_color is not supported.")
    if lower_color is not None and lower_color not in colors:
        raise ValueError("lower_color is not supported.")
    if upper_type is not None and upper_type not in clothing:
        raise ValueError("upper_type is not supported.")
    if backpack is not None and type(backpack) is not bool:
        raise ValueError("has_backpack must be boolean.")

    garments: list[str] = []
    if upper_color or upper_type:
        garment = " ".join(
            value for value in (upper_color, clothing.get(upper_type, "top")) if value
        )
        garments.append(garment)
    if lower_color:
        garments.append(f"{lower_color} pants")
    parts = [f"wearing {' and '.join(garments)}"] if garments else []
    if backpack is True:
        parts.append("carrying a backpack")
    elif backpack is False:
        parts.append("without a backpack")
    if not parts:
        raise ValueError("At least one attribute is required.")
    return "A person " + ", ".join(parts) + "."


def _repositories(work: UnitOfWork) -> Repositories:
    assert work.repositories is not None
    return work.repositories
