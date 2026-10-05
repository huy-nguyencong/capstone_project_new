"""ITM re-ranking of text search candidates: ordering, caching, fallbacks and API flag."""

from __future__ import annotations

import io
import uuid
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from person_search.services.searches import SearchResponse
from person_search.services.text_rerank import (
    MAX_RERANK_TOP_N,
    RerankSettings,
    TextRerankService,
)
from person_search.services.track_search import TrackSearchResult
from person_search.storage.contracts import BoundingBoxPixels

pytestmark = pytest.mark.unit


class FakeGateway:
    """Scores a candidate by the brightness of its crop: brighter wins."""

    def __init__(self) -> None:
        self.token_calls = 0
        self.itm_calls: list[tuple[str, int]] = []

    def image_tokens(self, content: bytes, *, version: str, dimension: int):
        self.token_calls += 1
        with Image.open(io.BytesIO(content)) as crop:
            level = crop.convert("L").getpixel((0, 0))
        tokens = np.zeros((577, 768), dtype=np.float16)
        tokens[0, 0] = level / 255
        return tokens

    def itm_scores(self, text: str, tokens, *, version: str, dimension: int):
        self.itm_calls.append((text, int(tokens.shape[0])))
        return [float(row[0, 0]) * 10 - 5 for row in tokens]


class FakeFrames:
    def __init__(self, levels: dict[str, int]) -> None:
        self.levels = levels
        self.reads = 0

    def get_frame(self, object_key: str) -> bytes:
        self.reads += 1
        image = Image.new("RGB", (40, 60), (self.levels[object_key],) * 3)
        buffer = io.BytesIO()
        image.save(buffer, format="JPEG")
        return buffer.getvalue()


def _result(key: str | None, score: float) -> TrackSearchResult:
    return TrackSearchResult(
        track_id=uuid.uuid4(),
        matching_score=score,
        camera_id=uuid.uuid4(),
        camera_name="C1",
        area_id=uuid.uuid4(),
        area_name="A",
        appeared_at_utc=datetime(2026, 10, 5, tzinfo=UTC),
        bbox=BoundingBoxPixels(x=5, y=5, width=20, height=40, frame_width=40, frame_height=60),
        frame_object_key=key,
    )


def test_pool_is_reordered_by_itm_and_scores_are_mapped_to_unit_interval(tmp_path: Path) -> None:
    gateway = FakeGateway()
    frames = FakeFrames({"dark": 20, "mid": 128, "bright": 240, "fourth": 60})
    service = TextRerankService(
        gateway, frames, settings=RerankSettings(top_n=3, cache_dir=tmp_path / "cache")
    )
    candidates = [
        _result("dark", 0.9),
        _result("mid", 0.8),
        _result("bright", 0.7),
        _result("fourth", 0.6),
    ]

    ranked = service.rerank("a man", candidates, keep=4, version="v", dimension=256)

    assert [r.frame_object_key for r in ranked] == ["bright", "mid", "dark", "fourth"]
    assert all(0.0 < r.matching_score < 1.0 for r in ranked[:3])
    assert ranked[0].matching_score > ranked[1].matching_score > ranked[2].matching_score
    assert ranked[3].matching_score == 0.6  # outside the pool: vector score kept
    assert gateway.itm_calls == [("a man", 3)]
    assert service.last_report is not None
    assert (service.last_report.cached, service.last_report.computed) == (0, 3)


def test_token_cache_is_written_and_reused(tmp_path: Path) -> None:
    gateway = FakeGateway()
    frames = FakeFrames({"a": 10, "b": 200})
    service = TextRerankService(
        gateway, frames, settings=RerankSettings(top_n=2, cache_dir=tmp_path / "cache")
    )
    candidates = [_result("a", 0.9), _result("b", 0.8)]

    service.rerank("a man", candidates, keep=2, version="v", dimension=256)
    again = service.rerank("a woman", candidates, keep=2, version="v", dimension=256)

    assert gateway.token_calls == 2
    assert frames.reads == 2
    assert sorted(p.name for p in (tmp_path / "cache").iterdir()) == sorted(
        f"{r.track_id}.npy" for r in candidates
    )
    assert [r.frame_object_key for r in again] == ["b", "a"]
    assert (service.last_report.cached, service.last_report.computed) == (2, 0)


def test_candidate_without_frame_is_kept_after_the_scored_ones(tmp_path: Path) -> None:
    gateway = FakeGateway()
    frames = FakeFrames({"x": 30, "y": 220})
    service = TextRerankService(
        gateway, frames, settings=RerankSettings(top_n=3, cache_dir=tmp_path / "cache")
    )
    candidates = [_result(None, 0.95), _result("x", 0.9), _result("y", 0.8)]

    ranked = service.rerank("a man", candidates, keep=3, version="v", dimension=256)

    assert [r.frame_object_key for r in ranked] == ["y", "x", None]
    assert ranked[2].matching_score == 0.95
    assert service.last_report.skipped == 1


def test_keep_cuts_after_reordering(tmp_path: Path) -> None:
    gateway = FakeGateway()
    frames = FakeFrames({"x": 30, "y": 220})
    service = TextRerankService(
        gateway, frames, settings=RerankSettings(top_n=2, cache_dir=tmp_path / "cache")
    )
    ranked = service.rerank(
        "a man", [_result("x", 0.9), _result("y", 0.8)], keep=1, version="v", dimension=256
    )
    assert [r.frame_object_key for r in ranked] == ["y"]


def test_settings_bounds() -> None:
    with pytest.raises(ValueError):
        RerankSettings(top_n=0, cache_dir=Path("."))
    with pytest.raises(ValueError):
        RerankSettings(top_n=MAX_RERANK_TOP_N + 1, cache_dir=Path("."))


def test_search_response_reports_rerank_flag() -> None:
    assert SearchResponse("TEXT", "a man", "v", 8, ()).reranked is False
    assert SearchResponse("TEXT", "a man", "v", 8, (), reranked=True).reranked is True
