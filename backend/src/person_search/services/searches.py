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
from typing import Any, Protocol
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
    reranked: bool = False


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
        rerank: Any = None,
    ) -> None:
        self._unit_of_work_factory = unit_of_work_factory
        self._milvus_client = milvus_client
        self._encoder = encoder
        # Optional TextRerankService: text and attribute searches take a larger candidate pool
        # from the vector search and return it in image-text matching order.
        self._rerank = rerank
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
        rerank = (
            self._rerank
            if mode in ("TEXT", "ATTRIBUTES")
            and prompt
            and config.encoder_version != DEMO_ENCODER_VERSION
            else None
        )
        if rerank is None:
            results = service.search(actor, query)
            return SearchResponse(mode, prompt, config.encoder_version, query.top_k, tuple(results))
        pool = max(query.top_k, rerank.settings.top_n)
        candidates = service.search(actor, query, pool=pool)
        results = rerank.rerank(
            prompt,
            candidates,
            keep=query.top_k,
            version=config.encoder_version,
            dimension=config.encoder_dimension,
        )
        return SearchResponse(
            mode, prompt, config.encoder_version, query.top_k, tuple(results), reranked=True
        )

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


# Attribute search vocabulary (English, CUHK-PEDES caption style). Values are the API enum;
# the text is what the prompt builder writes. The frontend mirrors this table exactly.
ATTRIBUTE_GENDERS = {"man": "man", "woman": "woman"}
ATTRIBUTE_UPPER_TYPES = {
    "t_shirt": "t-shirt",
    "shirt": "shirt",
    "sweater": "sweater",
    "jacket": "jacket",
    "coat": "coat",
    "dress": "dress",
}
ATTRIBUTE_UPPER_COLORS = frozenset(
    {
        "black",
        "white",
        "gray",
        "red",
        "pink",
        "purple",
        "orange",
        "yellow",
        "green",
        "blue",
        "navy",
        "brown",
        "beige",
    }
)
# Plural garments take no article ("blue jeans"); a skirt does ("a black skirt").
ATTRIBUTE_LOWER_TYPES = {"pants": "pants", "jeans": "jeans", "shorts": "shorts", "skirt": "skirt"}
ATTRIBUTE_LOWER_COLORS = frozenset(
    {"black", "white", "gray", "blue", "navy", "green", "brown", "beige", "khaki"}
)
# Each item maps to its full verb phrase: a suitcase is pulled, not carried.
ATTRIBUTE_CARRYING = {
    "backpack": "carrying a backpack",
    "handbag": "carrying a handbag",
    "shoulder_bag": "carrying a shoulder bag",
    "suitcase": "pulling a suitcase",
}
ATTRIBUTE_FIELDS = frozenset(
    {"gender", "upper_type", "upper_color", "lower_type", "lower_color", "carrying"}
)


def _with_article(phrase: str) -> str:
    return ("an " if phrase[0] in "aeiou" else "a ") + phrase


def _choice(attributes: Mapping[str, object], field: str, allowed) -> str | None:
    value = attributes.get(field)
    if value is not None and value not in allowed:
        raise ValueError(f"{field} is not supported.")
    return value  # type: ignore[return-value]


def attributes_prompt(attributes: Mapping[str, object]) -> str:
    """Build the English caption sent to the Text Encoder from the selected attributes.

    Negations ("without a backpack") are deliberately not offered: CLIP-style text encoders
    match the noun and would rank people carrying one higher.
    """

    if not attributes or set(attributes) - ATTRIBUTE_FIELDS:
        raise ValueError("Attributes contain unsupported fields.")
    gender = _choice(attributes, "gender", ATTRIBUTE_GENDERS)
    upper_type = _choice(attributes, "upper_type", ATTRIBUTE_UPPER_TYPES)
    upper_color = _choice(attributes, "upper_color", ATTRIBUTE_UPPER_COLORS)
    lower_type = _choice(attributes, "lower_type", ATTRIBUTE_LOWER_TYPES)
    lower_color = _choice(attributes, "lower_color", ATTRIBUTE_LOWER_COLORS)
    carrying = _choice(attributes, "carrying", ATTRIBUTE_CARRYING)
    if upper_type == "dress" and (lower_type or lower_color):
        raise ValueError("A dress cannot be combined with lower clothing.")
    if not any((gender, upper_type, upper_color, lower_type, lower_color, carrying)):
        raise ValueError("At least one attribute is required.")

    garments: list[str] = []
    if upper_type or upper_color:
        words = [upper_color, ATTRIBUTE_UPPER_TYPES[upper_type] if upper_type else "top"]
        garments.append(_with_article(" ".join(word for word in words if word)))
    if lower_type or lower_color:
        noun = ATTRIBUTE_LOWER_TYPES[lower_type] if lower_type else "pants"
        phrase = " ".join(word for word in (lower_color, noun) if word)
        garments.append(_with_article(phrase) if noun == "skirt" else phrase)
    parts = [f"wearing {' and '.join(garments)}"] if garments else []
    if carrying:
        parts.append(ATTRIBUTE_CARRYING[carrying])
    subject = f"A {ATTRIBUTE_GENDERS[gender]}" if gender else "A person"
    return f"{subject} {', '.join(parts)}." if parts else f"{subject}."


def _repositories(work: UnitOfWork) -> Repositories:
    assert work.repositories is not None
    return work.repositories
