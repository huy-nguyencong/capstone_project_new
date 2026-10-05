"""Production query inference over the shared RaSa image/text vector space."""

from __future__ import annotations

import re
from collections.abc import Callable, Sequence
from pathlib import Path

from person_search.ai.encoders.image import (
    ImageEncoderBackend,
    ImageEncoderSettings,
    RasaImageEncoder,
    RasaImageProcessBackend,
    RasaImageQueryGateway,
)
from person_search.ai.encoders.rasa import RasaRuntimeFactory, RasaRuntimeSettings
from person_search.ai.registry import EncoderEntry
from person_search.workers.contracts import EmbeddingVector, ModelLineage
from person_search.workers.errors import AIErrorCode, AIWorkerError

MAX_QUERY_TEXT_CHARACTERS = 500
_ENGLISH_DESCRIPTION = re.compile(r"^[A-Za-z0-9][A-Za-z0-9 .,;:'\"()/-]*$")


def validate_english_description(text: str) -> str:
    """Enforce the v1 English-only contract without translating user input."""

    if not isinstance(text, str) or not text.strip():
        raise ValueError("Text query must not be empty.")
    normalized = " ".join(text.split())
    if len(normalized) > MAX_QUERY_TEXT_CHARACTERS:
        raise ValueError("Text query is too long.")
    if not _ENGLISH_DESCRIPTION.fullmatch(normalized) or not any(
        character.isalpha() for character in normalized
    ):
        raise ValueError("Text query must be an English description using supported characters.")
    return normalized


class RasaQueryInferenceGateway:
    """Serve image and English text queries from one loaded RaSa process."""

    def __init__(
        self,
        image_encoder: RasaImageEncoder,
        backend: ImageEncoderBackend,
    ) -> None:
        self.image_encoder = image_encoder
        self._backend = backend
        self._image_gateway = RasaImageQueryGateway(image_encoder)

    @property
    def lineage(self) -> ModelLineage:
        return self.image_encoder.lineage

    def open(self) -> None:
        self.image_encoder.open()

    def image(self, content: bytes, *, version: str, dimension: int) -> Sequence[float]:
        return self._image_gateway.image(content, version=version, dimension=dimension)

    def text(self, text: str, *, version: str, dimension: int) -> Sequence[float]:
        self._require_vector_space(version, dimension)
        normalized = validate_english_description(text)
        try:
            raw = self._backend.encode_text(
                normalized,
                timeout_seconds=self.image_encoder.settings.inference_timeout_seconds,
            )
        except Exception as exc:
            self.close()
            raise AIWorkerError(AIErrorCode.TEXT_ENCODER_INFERENCE_FAILED, cause=exc) from exc
        try:
            return EmbeddingVector(tuple(raw), dimension, True, self.lineage).values
        except (TypeError, ValueError) as exc:
            self.close()
            raise AIWorkerError(AIErrorCode.TEXT_ENCODER_OUTPUT_INVALID, cause=exc) from exc

    def image_tokens(self, content: bytes, *, version: str, dimension: int):
        """Image token features (577, 768) of an uploaded crop, for ITM re-ranking."""

        self._require_vector_space(version, dimension)
        from person_search.services.searches import decode_query_image

        image = decode_query_image(content)
        try:
            return self._backend.encode_tokens(
                image, timeout_seconds=self.image_encoder.settings.inference_timeout_seconds
            )
        except Exception as exc:
            self.close()
            raise AIWorkerError(AIErrorCode.IMAGE_ENCODER_INFERENCE_FAILED, cause=exc) from exc
        finally:
            image.close()

    def itm_scores(self, text: str, tokens, *, version: str, dimension: int) -> Sequence[float]:
        """Matching logits of one English sentence against candidate image tokens (N, 577, 768)."""

        self._require_vector_space(version, dimension)
        normalized = validate_english_description(text)
        # One fusion pass per candidate; allow the whole pool within the inference timeout each.
        count = max(1, int(getattr(tokens, "shape", (1,))[0]))
        try:
            return list(
                self._backend.itm_scores(
                    normalized,
                    tokens,
                    timeout_seconds=self.image_encoder.settings.inference_timeout_seconds * count,
                )
            )
        except Exception as exc:
            self.close()
            raise AIWorkerError(AIErrorCode.TEXT_ENCODER_INFERENCE_FAILED, cause=exc) from exc

    def _require_vector_space(self, version: str, dimension: int) -> None:
        if version != self.lineage.version or dimension != self.image_encoder.dimension:
            raise ValueError("Query encoder metadata does not match the active vector space.")

    def close(self) -> None:
        self.image_encoder.close()


def build_rasa_query_gateway(
    entry: EncoderEntry,
    *,
    artifact_root: str | Path,
    runtime_settings: RasaRuntimeSettings,
    device: str = "cpu",
    settings: ImageEncoderSettings | None = None,
    backend_factory: Callable[..., ImageEncoderBackend] = RasaImageProcessBackend,
    keep_fusion_layers: bool = False,
) -> RasaQueryInferenceGateway:
    """Build image/text query inference with one verified checkpoint and process.

    ``keep_fusion_layers`` loads the cross-modal layers and the matching head as well (about
    0.25 GiB more), which the ITM re-ranking of text searches needs.
    """

    RasaRuntimeFactory(
        entry,
        artifact_root=artifact_root,
        settings=runtime_settings,
        device=device,
    )
    selected = settings or ImageEncoderSettings()
    backend_kwargs = {"keep_fusion_layers": True} if keep_fusion_layers else {}
    backend = backend_factory(
        entry,
        artifact_root=artifact_root,
        runtime_settings=runtime_settings,
        device=device,
        settings=selected,
        **backend_kwargs,
    )
    image_encoder = RasaImageEncoder(
        backend,
        lineage=ModelLineage(entry.id, entry.version, entry.artifact.sha256),
        dimension=entry.dimension,
        settings=selected,
    )
    return RasaQueryInferenceGateway(image_encoder, backend)
