"""Deterministic synthetic adapters that must never be used as production AI."""

from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass, field
from typing import Final

from person_search.storage.contracts import (
    BoundingBoxPixels,
    EncoderManifest,
    TrackIngestionRequest,
)
from person_search.workers.contracts import Detection, ModelLineage, SampledFrame, SourceFrame
from person_search.workers.pipeline import Pipeline

DEMO_ENCODER_VERSION: Final = "fake_demo_v1"
DEMO_ENCODER_SHA256: Final = "eed9d600efbe54cebfb11d6bc78260fd41e2d7b652ce1ed389600fade8b6cf83"
DEMO_FIXTURE_ID: Final = "central-person-v1"


@dataclass(frozen=True, slots=True)
class SyntheticMetadata:
    """Marker kept on demo-only objects and deliberately excluded from storage DTOs."""

    synthetic: bool = True
    fixture_id: str = DEMO_FIXTURE_ID

    def __post_init__(self) -> None:
        if self.synthetic is not True:
            raise ValueError("Demo metadata must remain marked as synthetic.")
        if not self.fixture_id:
            raise ValueError("Demo fixture_id must be non-empty.")


SYNTHETIC_METADATA: Final = SyntheticMetadata()


@dataclass(frozen=True, slots=True)
class DemoCompletedTrack:
    """Legacy demo track output, isolated until AIW-16 replaces orchestration."""

    key: str
    started_ms: int
    ended_ms: int
    representative: SourceFrame
    bbox: BoundingBoxPixels
    synthetic_metadata: SyntheticMetadata = field(default=SYNTHETIC_METADATA)


@dataclass(frozen=True, slots=True)
class DemoTrackIngestionRequest(TrackIngestionRequest):
    """Track request carrying a non-persisted marker for demo/test assertions."""

    synthetic_metadata: SyntheticMetadata = field(default=SYNTHETIC_METADATA)


class DemoDetector:
    """Synthetic central box; deliberately not a person detector."""

    lineage = ModelLineage("demo_detector", "1", "0" * 64)
    synthetic_metadata = SYNTHETIC_METADATA

    def detect(self, frame: SampledFrame):
        width, height = frame.image.size
        return [
            Detection(
                bbox=BoundingBoxPixels(
                    width // 4,
                    height // 4,
                    max(1, width // 2),
                    max(1, height // 2),
                    width,
                    height,
                ),
                class_id=0,
                class_name="person",
                confidence=1.0,
                detector=self.lineage,
            )
        ]


class DemoTracker:
    """One synthetic track per five sampled frames with deterministic output."""

    synthetic_metadata = SYNTHETIC_METADATA

    def __init__(self):
        self.first = None
        self.count = 0
        self.last_ms = 0

    def update(self, frame: SampledFrame, boxes):
        if not boxes:
            return []
        if self.first is None:
            self.first = (frame.source, boxes[0].bbox)
        self.last_ms = frame.timestamp_ms
        self.count += 1
        return self.finish() if self.count == 5 else []

    def finish(self):
        if self.first is None:
            return []
        frame, bbox = self.first
        result = DemoCompletedTrack(str(frame.index), frame.timestamp_ms, self.last_ms, frame, bbox)
        self.close()
        return [result]

    def close(self):
        self.first, self.count, self.last_ms = None, 0, 0


class DemoEncoder:
    """Deterministic image hash vector; deliberately not a learned encoder."""

    synthetic_metadata = SYNTHETIC_METADATA

    def encode(self, crop):
        digest = hashlib.sha256(crop.resize((16, 16)).tobytes()).digest()
        values = [float(digest[index % 32] + 1) for index in range(256)]
        return _normalized(values)


class DemoEncoderGateway:
    """Deterministic image/text query adapter for explicitly enabled demo mode."""

    synthetic_metadata = SYNTHETIC_METADATA

    def image(self, content: bytes, *, version: str, dimension: int):
        _require_demo_encoder(version, dimension)
        # Delayed import avoids coupling production search module import to demo adapters.
        from person_search.services.searches import decode_query_image

        image = decode_query_image(content)
        digest = hashlib.sha256(image.resize((16, 16)).tobytes()).digest()
        return _normalized([float(digest[index % len(digest)] + 1) for index in range(dimension)])

    def text(self, text: str, *, version: str, dimension: int):
        _require_demo_encoder(version, dimension)
        digest = hashlib.sha256(text.encode("utf-8")).digest()
        return _normalized([float(digest[index % len(digest)] + 1) for index in range(dimension)])


class DemoPipeline(Pipeline):
    """Pipeline whose request type retains a synthetic marker until ingestion."""

    request_type = DemoTrackIngestionRequest
    synthetic_metadata = SYNTHETIC_METADATA


def build_demo_pipeline(config) -> DemoPipeline:
    """Build the fake pipeline only after the complete demo config is verified."""

    if (
        config.detector_name != "demo_detector"
        or config.detector_version != "1"
        or config.tracker_version != "1"
        or config.tracker_name != "demo_tracker"
        or config.encoder_version != DEMO_ENCODER_VERSION
        or config.encoder_dimension != 256
        or config.checkpoint_sha256 != DEMO_ENCODER_SHA256
    ):
        raise ValueError("Demo worker requires the isolated demo model configuration")
    return DemoPipeline(
        DemoDetector(),
        DemoTracker(),
        DemoEncoder(),
        EncoderManifest(DEMO_ENCODER_VERSION, 256, DEMO_ENCODER_SHA256),
    )


def _require_demo_encoder(version: str, dimension: int) -> None:
    if version != DEMO_ENCODER_VERSION or dimension != 256:
        from person_search.services.searches import EncoderUnavailableError

        raise EncoderUnavailableError("Demo encoder cannot serve the active model.")


def _normalized(values: list[float]) -> list[float]:
    norm = math.sqrt(sum(value * value for value in values))
    return [value / norm for value in values]
