"""Deterministic coverage for explicitly opt-in synthetic AI adapters."""

from __future__ import annotations

import math
import uuid
from pathlib import Path
from types import SimpleNamespace

import pytest
from PIL import Image

from person_search.ai.registry import load_registry
from person_search.demo import (
    DEMO_ENCODER_SHA256,
    DemoDetector,
    DemoEncoder,
    DemoTracker,
    build_demo_pipeline,
)
from person_search.workers.contracts import SampledFrame, SourceFrame

pytestmark = [pytest.mark.unit, pytest.mark.contract]


def _frame(index: int = 0) -> SourceFrame:
    return SourceFrame(
        camera_id=uuid.UUID("00000000-0000-4000-8000-000000000001"),
        source_frame_index=index,
        source_timestamp_ms=index * 40,
        image=Image.new("RGB", (64, 48), "red"),
        width=64,
        height=48,
    )


def _sample(index: int = 0) -> SampledFrame:
    return SampledFrame(_frame(index * 10), sampling_interval=10, sample_sequence=index)


def _config() -> SimpleNamespace:
    return SimpleNamespace(
        detector_name="demo_detector",
        detector_version="1",
        tracker_name="demo_tracker",
        tracker_version="1",
        encoder_name="demo_encoder",
        encoder_version="fake_demo_v1",
        encoder_dimension=256,
        checkpoint_sha256=DEMO_ENCODER_SHA256,
    )


def test_demo_adapters_produce_known_synthetic_fixture_offline() -> None:
    detector = DemoDetector()
    tracker = DemoTracker()
    encoder = DemoEncoder()

    detections = detector.detect(_sample())
    assert len(detections) == 1
    box = detections[0].bbox
    assert (box.x, box.y, box.width, box.height, box.frame_width, box.frame_height) == (
        16,
        12,
        32,
        24,
        64,
        48,
    )

    tracks = []
    for index in range(5):
        frame = _sample(index)
        tracks.extend(tracker.update(frame, detector.detect(frame)))
    assert len(tracks) == 1
    assert tracks[0].key == "0"
    assert tracks[0].started_ms == 0
    assert tracks[0].ended_ms == 1600
    assert tracks[0].synthetic_metadata.synthetic is True

    crop = _frame().image.crop((16, 12, 48, 36))
    first = encoder.encode(crop)
    second = encoder.encode(crop)
    assert first == second
    assert len(first) == 256
    assert math.isclose(math.sqrt(sum(value * value for value in first)), 1.0)
    assert detector.synthetic_metadata == tracker.synthetic_metadata == encoder.synthetic_metadata


def test_demo_registry_and_pipeline_require_explicit_offline_profile() -> None:
    manifest = Path(__file__).parents[2] / "config" / "models.demo.json"
    registry = load_registry(manifest, allow_demo=True)
    selection = registry.resolve("demo_detector", "demo_tracker")
    pipeline = build_demo_pipeline(_config())

    assert selection.encoder.id == "demo_encoder"
    assert pipeline.synthetic_metadata.synthetic is True
    with pytest.raises(ValueError, match="isolated demo model configuration"):
        build_demo_pipeline(SimpleNamespace(**{**vars(_config()), "tracker_name": "bytetrack"}))
