from __future__ import annotations

import uuid

import pytest
from PIL import Image

from person_search.workers.contracts import SampledFrame, SourceFrame
from person_search.workers.sampling import (
    FrameSampler,
    sampling_interval_for_profile,
    sampling_profile_for_interval,
)

pytestmark = pytest.mark.unit


def _frame(index: int, timestamp_ms: int | None = None) -> SourceFrame:
    return SourceFrame(
        camera_id=uuid.UUID("00000000-0000-4000-8000-000000000001"),
        source_frame_index=index,
        source_timestamp_ms=index * 40 if timestamp_ms is None else timestamp_ms,
        image=Image.new("RGB", (8, 6)),
        width=8,
        height=6,
    )


@pytest.mark.parametrize(
    ("interval", "count", "expected"),
    [
        (10, 7, [0]),
        (10, 21, [0, 10, 20]),
        (20, 41, [0, 20, 40]),
    ],
)
def test_first_frame_and_index_boundaries_are_deterministic(interval, count, expected) -> None:
    sampled = list(FrameSampler(interval).select(_frame(index) for index in range(count)))

    assert [frame.source_frame_index for frame in sampled] == expected
    assert [frame.sample_sequence for frame in sampled] == list(range(len(expected)))
    assert all(frame.sampling_interval == interval for frame in sampled)


def test_variable_source_timestamps_are_preserved_not_reconstructed() -> None:
    source = [_frame(0, 17), _frame(1, 35), _frame(2, 104), _frame(3, 105)]

    sampled = list(FrameSampler.for_benchmark(2).select(source))

    assert [frame.source_timestamp_ms for frame in sampled] == [17, 104]
    assert sampled[1].source is source[2]


@pytest.mark.parametrize("interval", [0, -1, True, 1.5, "10"])
def test_invalid_intervals_are_rejected(interval) -> None:
    with pytest.raises(ValueError, match="positive integer"):
        FrameSampler(interval)


def test_production_profiles_are_allowlisted_and_benchmark_override_is_isolated() -> None:
    assert sampling_interval_for_profile(None) == 20
    assert sampling_interval_for_profile("baseline") == 10
    assert sampling_interval_for_profile("throughput") == 20
    assert sampling_profile_for_interval(10) == "baseline"
    assert sampling_profile_for_interval(20) == "throughput"
    assert sampling_profile_for_interval(3) is None
    assert FrameSampler.from_production_profile().sampling_interval == 20
    assert FrameSampler.for_benchmark(3).sampling_interval == 3
    with pytest.raises(ValueError, match="Unknown production"):
        FrameSampler.from_production_profile("3")


def test_sample_contract_rejects_sequence_unrelated_to_source_index() -> None:
    with pytest.raises(ValueError, match="map exactly"):
        SampledFrame(_frame(10), sampling_interval=10, sample_sequence=2)
