from __future__ import annotations

import json
import uuid
from pathlib import Path

import pytest
from PIL import Image, ImageDraw, ImageFilter

from person_search.ai.selectors import (
    RepresentativeFrameSelector,
    SelectorSettings,
    crop_representative,
    load_selector_settings,
)
from person_search.storage.contracts import BoundingBoxPixels
from person_search.workers.contracts import (
    ModelLineage,
    QualityFlag,
    SampledFrame,
    SourceFrame,
    TrackState,
    TrackUpdate,
)
from person_search.workers.errors import AIErrorCode, AIWorkerError

pytestmark = pytest.mark.unit

SHA = "a" * 64


def lineage(name: str) -> ModelLineage:
    return ModelLineage(name, "1", SHA)


def textured_image(size=(80, 100), *, blur=False) -> Image.Image:
    image = Image.new("RGB", size, "white")
    draw = ImageDraw.Draw(image)
    for x in range(0, size[0], 4):
        draw.rectangle((x, 0, x + 1, size[1]), fill="black")
    return image.filter(ImageFilter.GaussianBlur(5)) if blur else image


def frame(
    sequence: int,
    camera_id: uuid.UUID,
    *,
    timestamp_ms: int | None = None,
    image: Image.Image | None = None,
) -> SampledFrame:
    selected = image or textured_image()
    source = SourceFrame(
        camera_id,
        sequence * 10,
        sequence * 400 if timestamp_ms is None else timestamp_ms,
        selected,
        selected.width,
        selected.height,
    )
    return SampledFrame(source, 10, sequence)


def update(
    sampled: SampledFrame,
    local_id: str = "bt-1",
    *,
    state=TrackState.ACTIVE,
    bbox: BoundingBoxPixels | None = None,
) -> TrackUpdate:
    selected_bbox = bbox or BoundingBoxPixels(20, 15, 32, 70, sampled.width, sampled.height)
    return TrackUpdate(
        local_id,
        sampled.camera_id,
        selected_bbox,
        sampled.source_frame_index,
        sampled.source_timestamp_ms,
        state,
        lineage("tracker"),
    )


def selector(**overrides) -> RepresentativeFrameSelector:
    defaults = {
        "minimum_bbox_width": 8,
        "minimum_bbox_height": 8,
        "minimum_sharpness_variance": 0.01,
    }
    defaults.update(overrides)
    subject = RepresentativeFrameSelector(
        processing_job_id=uuid.uuid4(),
        ai_config_version_id=uuid.uuid4(),
        detector=lineage("detector"),
        tracker=lineage("tracker"),
        encoder=lineage("encoder"),
        settings=SelectorSettings(**defaults),
    )
    subject.open()
    return subject


def test_keeps_top_three_and_prefers_stable_middle_candidate() -> None:
    camera_id = uuid.uuid4()
    subject = selector(max_candidates_per_track=3)
    frames = [frame(index, camera_id) for index in range(5)]
    for sampled in frames:
        subject.consider(sampled, update(sampled))

    assert subject.metrics.buffered_candidates == 3
    assert subject.metrics.evicted_candidates == 2
    completed = subject.flush()[0]

    assert completed.quality_flag is QualityFlag.ACCEPTED
    assert completed.representative.frame.source_frame_index in {10, 20, 30}
    assert {item.name for item in completed.representative.quality_components} == {
        "person_resolution",
        "sharpness",
        "body_completeness",
        "detection_track_stability",
        "temporal_preference",
        "border_clipping_penalty",
        "occlusion_penalty",
    }


def test_tie_break_uses_smaller_source_frame_index() -> None:
    camera_id = uuid.uuid4()
    subject = selector(max_candidates_per_track=3)
    warmup = frame(0, camera_id, timestamp_ms=0)
    first = frame(1, camera_id, timestamp_ms=100)
    second = frame(2, camera_id, timestamp_ms=100)
    for sampled in (warmup, first, second):
        subject.consider(sampled, update(sampled))
    completed = subject.flush()[0]

    assert completed.representative.frame.source_frame_index == first.source_frame_index


def test_blurry_or_tiny_candidates_fall_back_with_low_quality() -> None:
    camera_id = uuid.uuid4()
    subject = selector(minimum_sharpness_variance=10_000)
    sampled = frame(0, camera_id, image=Image.new("RGB", (80, 100), "gray"))
    tiny = BoundingBoxPixels(10, 10, 6, 6, 80, 100)
    subject.consider(sampled, update(sampled, bbox=tiny))

    completed = subject.flush()[0]

    assert completed.quality_flag is QualityFlag.LOW_QUALITY
    assert completed.representative.bbox == tiny


def test_shared_frame_is_counted_once_for_multiple_tracks() -> None:
    camera_id = uuid.uuid4()
    subject = selector()
    sampled = frame(0, camera_id)
    subject.consider(sampled, update(sampled, "bt-1"))
    subject.consider(sampled, update(sampled, "bt-2"))

    assert subject.metrics.buffered_frames == 1
    assert subject.metrics.buffered_candidates == 2
    assert subject.metrics.buffered_bytes == 80 * 100 * 3
    completed = subject.flush()
    assert completed[0].representative.frame.image is completed[1].representative.frame.image


def test_overlapping_tracks_receive_occlusion_penalty() -> None:
    camera_id = uuid.uuid4()
    subject = selector()
    sampled = frame(0, camera_id)
    subject.consider(sampled, update(sampled, "bt-1"))
    overlap = BoundingBoxPixels(24, 18, 32, 70, sampled.width, sampled.height)
    subject.consider(sampled, update(sampled, "bt-2", bbox=overlap))

    completed = subject.flush()
    for track in completed:
        components = {
            item.name: item.value for item in track.representative.quality_components
        }
        assert components["occlusion_penalty"] > 0


def test_abnormal_bbox_change_is_excluded_by_hard_filter() -> None:
    camera_id = uuid.uuid4()
    subject = selector(
        minimum_sharpness_variance=1_000_000_000,
        maximum_area_change_ratio=2,
    )
    first, second = frame(0, camera_id), frame(1, camera_id)
    subject.consider(first, update(first))
    changed = BoundingBoxPixels(5, 5, 70, 90, second.width, second.height)
    subject.consider(second, update(second, bbox=changed))

    assert subject.flush()[0].quality_flag is QualityFlag.LOW_QUALITY


def test_global_memory_pressure_evicts_lowest_candidate() -> None:
    camera_id = uuid.uuid4()
    subject = selector(max_buffer_bytes=80 * 100 * 3)
    first, second = frame(0, camera_id), frame(1, camera_id)
    subject.consider(first, update(first))
    subject.consider(second, update(second))

    assert subject.metrics.buffered_frames == 1
    assert subject.metrics.buffered_candidates == 1
    assert subject.metrics.evicted_candidates == 1
    assert subject.flush()


def test_frame_larger_than_budget_fails_before_retention() -> None:
    camera_id = uuid.uuid4()
    subject = selector(max_buffer_bytes=100)
    sampled = frame(0, camera_id)

    with pytest.raises(AIWorkerError) as caught:
        subject.consider(sampled, update(sampled))

    assert caught.value.code is AIErrorCode.RESOURCE_EXHAUSTED
    assert subject.metrics.buffered_bytes == 0


def test_ended_update_finalizes_and_cancel_close_does_not_emit() -> None:
    camera_id = uuid.uuid4()
    subject = selector()
    sampled = frame(0, camera_id)
    subject.consider(sampled, update(sampled))
    subject.consider(sampled, update(sampled, state=TrackState.ENDED))
    assert len(subject.flush()) == 1

    cancelled = selector()
    cancelled.consider(sampled, update(sampled))
    cancelled.close()
    assert cancelled.metrics.buffered_bytes == 0
    with pytest.raises(RuntimeError, match="before flush"):
        cancelled.flush()


def test_crop_padding_is_clamped_and_does_not_mutate_full_frame() -> None:
    camera_id = uuid.uuid4()
    subject = selector()
    sampled = frame(0, camera_id)
    border = BoundingBoxPixels(0, 0, 20, 30, 80, 100)
    subject.consider(sampled, update(sampled, bbox=border))
    representative = subject.flush()[0].representative

    crop = crop_representative(representative, padding_ratio=0.5)
    try:
        assert crop.size == (30, 45)
        assert representative.frame.image.size == (80, 100)
    finally:
        crop.close()


def test_settings_loader_rejects_unknown_fields(tmp_path: Path) -> None:
    source = Path(__file__).parents[2] / "config" / "representative_selector.json"
    assert load_selector_settings(source).max_candidates_per_track == 3
    payload = json.loads(source.read_text(encoding="utf-8"))
    payload["unknown"] = True
    path = tmp_path / "selector.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValueError, match="missing or unknown"):
        load_selector_settings(path)
