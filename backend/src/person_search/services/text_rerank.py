"""Re-rank the candidates of a text or attribute search with RaSa's image-text matching head.

The vector search compares RaSa's contrastive embeddings, which the model uses only to produce
candidates; its published accuracy comes from the cross-modal matching (ITM) stage that scores
each (text, image) pair through the fusion layers (Section 8.2 of the report). This service
takes the first ``top_n`` candidates of the vector search, fetches each representative frame,
crops the person exactly as the index did, turns the crop into image token features through
the query encoder process, scores every candidate against the query sentence, and returns the
candidates in ITM order with the matching logit mapped to 0..1 as the relevance score.

Token features of a track never change, so they are cached on disk (``<track_id>.npy``,
float16, about 0.9 MB each); the first search over a track pays the image encoder (about
1.3 s on the CPU), later searches only the matching head (about 0.15 s per candidate).
"""

from __future__ import annotations

import io
import logging
import math
import time
from collections.abc import Sequence
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, Protocol
from uuid import UUID

from PIL import Image

from person_search.services.track_imagery import FrameReader
from person_search.services.track_search import TrackSearchResult

logger = logging.getLogger(__name__)

MAX_RERANK_TOP_N = 128  # the authors evaluate RaSa with ITM over the top 128 (k_test)


class RerankGateway(Protocol):
    def image_tokens(self, content: bytes, *, version: str, dimension: int) -> Any: ...

    def itm_scores(
        self, text: str, tokens: Any, *, version: str, dimension: int
    ) -> Sequence[float]: ...


@dataclass(frozen=True, slots=True)
class RerankSettings:
    top_n: int
    cache_dir: Path

    def __post_init__(self) -> None:
        if isinstance(self.top_n, bool) or not isinstance(self.top_n, int):
            raise ValueError("top_n must be an integer.")
        if not 1 <= self.top_n <= MAX_RERANK_TOP_N:
            raise ValueError(f"top_n must be between 1 and {MAX_RERANK_TOP_N}.")


@dataclass(frozen=True, slots=True)
class RerankReport:
    candidates: int
    cached: int
    computed: int
    skipped: int
    seconds: float


class RerankUnavailableError(RuntimeError):
    pass


class TextRerankService:
    def __init__(
        self,
        gateway: RerankGateway,
        frames: FrameReader,
        *,
        settings: RerankSettings,
    ) -> None:
        self._gateway = gateway
        self._frames = frames
        self.settings = settings
        self.last_report: RerankReport | None = None

    def rerank(
        self,
        text: str,
        results: Sequence[TrackSearchResult],
        *,
        keep: int,
        version: str,
        dimension: int,
    ) -> list[TrackSearchResult]:
        """Return ``keep`` results: the ITM-ordered pool first, then the rest in vector order."""

        started = time.perf_counter()
        pool = list(results[: self.settings.top_n])
        rest = list(results[self.settings.top_n :])
        tokens, scored, cached, computed = [], [], 0, 0
        for result in pool:
            try:
                array, from_cache = self._tokens(result, version=version, dimension=dimension)
            except Exception as error:
                logger.warning(
                    "rerank candidate skipped",
                    extra={"track_id": str(result.track_id), "error_type": type(error).__name__},
                )
                continue
            cached += from_cache
            computed += not from_cache
            tokens.append(array)
            scored.append(result)
        skipped = len(pool) - len(scored)
        if not scored:
            self.last_report = RerankReport(len(pool), 0, 0, skipped, time.perf_counter() - started)
            return list(results[:keep])
        import numpy as np

        logits = self._gateway.itm_scores(
            text, np.stack(tokens), version=version, dimension=dimension
        )
        if len(logits) != len(scored):
            raise RerankUnavailableError("ITM returned a score count that does not match.")
        order = sorted(range(len(scored)), key=lambda index: -float(logits[index]))
        reordered = [
            replace(scored[index], matching_score=_sigmoid(float(logits[index]))) for index in order
        ]
        unscored = [result for result in pool if result not in scored]
        final = reordered + unscored + rest
        self.last_report = RerankReport(
            len(pool), cached, computed, skipped, round(time.perf_counter() - started, 3)
        )
        return final[:keep]

    def _tokens(self, result: TrackSearchResult, *, version: str, dimension: int):
        import numpy as np

        path = self._cache_path(result.track_id)
        if path.is_file():
            try:
                array = np.load(path)
                if array.shape == (577, 768):
                    return array, True
            except (OSError, ValueError):
                pass
        if not result.frame_object_key:
            raise RerankUnavailableError("Result has no stored frame.")
        content = self._frames.get_frame(result.frame_object_key)
        with Image.open(io.BytesIO(content)) as frame:
            box = result.bbox
            crop = frame.convert("RGB").crop((box.x, box.y, box.x + box.width, box.y + box.height))
        try:
            buffer = io.BytesIO()
            crop.save(buffer, format="PNG")
        finally:
            crop.close()
        array = np.asarray(
            self._gateway.image_tokens(buffer.getvalue(), version=version, dimension=dimension),
            dtype=np.float16,
        )
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            np.save(path, array)
        except OSError as error:
            logger.warning("rerank token cache not written", extra={"error": str(error)})
        return array, False

    def _cache_path(self, track_id: UUID) -> Path:
        return self.settings.cache_dir / f"{track_id}.npy"


def _sigmoid(value: float) -> float:
    return 1.0 / (1.0 + math.exp(-value))
