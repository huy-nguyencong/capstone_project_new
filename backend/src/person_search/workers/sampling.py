"""Deterministic source-frame sampling and production profile mapping."""

from __future__ import annotations

from collections.abc import Iterable, Iterator
from types import MappingProxyType
from typing import Final

from person_search.workers.contracts import SampledFrame, SourceFrame

BASELINE_SAMPLING_PROFILE: Final = "baseline"
PRODUCTION_SAMPLING_PROFILES: Final = MappingProxyType(
    {
        BASELINE_SAMPLING_PROFILE: 10,
        "throughput": 20,
    }
)


def sampling_interval_for_profile(profile: str | None) -> int:
    """Resolve an Admin-facing allowlisted profile to its immutable interval."""

    selected = BASELINE_SAMPLING_PROFILE if profile is None else profile
    if not isinstance(selected, str) or selected not in PRODUCTION_SAMPLING_PROFILES:
        raise ValueError("Unknown production sampling profile.")
    return PRODUCTION_SAMPLING_PROFILES[selected]


def sampling_profile_for_interval(interval: int) -> str | None:
    """Describe a persisted production snapshot without guessing benchmark values."""

    return next(
        (
            name
            for name, configured in PRODUCTION_SAMPLING_PROFILES.items()
            if configured == interval
        ),
        None,
    )


class FrameSampler:
    """Pure 0-based sampler: select source indices where ``index % N == 0``."""

    def __init__(self, sampling_interval: int) -> None:
        if (
            isinstance(sampling_interval, bool)
            or not isinstance(sampling_interval, int)
            or sampling_interval < 1
        ):
            raise ValueError("sampling_interval must be a positive integer.")
        self.sampling_interval = sampling_interval

    @classmethod
    def from_production_profile(cls, profile: str | None = None) -> FrameSampler:
        return cls(sampling_interval_for_profile(profile))

    @classmethod
    def for_benchmark(cls, sampling_interval: int) -> FrameSampler:
        """Explicit escape hatch for offline evaluation; never used by the upload API."""

        return cls(sampling_interval)

    def sample(self, frame: SourceFrame) -> SampledFrame | None:
        if not isinstance(frame, SourceFrame):
            raise TypeError("FrameSampler accepts SourceFrame values only.")
        if frame.source_frame_index % self.sampling_interval:
            return None
        return SampledFrame(
            source=frame,
            sampling_interval=self.sampling_interval,
            sample_sequence=frame.source_frame_index // self.sampling_interval,
        )

    def select(self, frames: Iterable[SourceFrame]) -> Iterator[SampledFrame]:
        for frame in frames:
            if (sampled := self.sample(frame)) is not None:
                yield sampled
