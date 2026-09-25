"""Frame source and replaceable detector/tracker/encoder interfaces for BE-10."""

import hashlib
import io
import math
import uuid
from dataclasses import dataclass
from datetime import UTC
from typing import Protocol

import av
from PIL import Image

from person_search.storage.contracts import (
    BoundingBoxPixels,
    EncoderManifest,
    TrackIngestionRequest,
)


@dataclass(frozen=True)
class SourceFrame:
    index: int
    timestamp_ms: int
    image: Image.Image | None


class FrameSource(Protocol):
    def frames(self, source, sampling): ...


class VideoFrameSource:
    def frames(self, source, sampling):
        # Upload source is always a private local file, never a client supplied URL.
        with av.open(str(source), options={"protocol_whitelist": "file"}) as container:
            stream = container.streams.video[0]
            first_pts = None
            previous_ms = 0
            for index, frame in enumerate(container.decode(stream)):
                if frame.pts is None or frame.time_base is None:
                    raise ValueError("Video frame is missing timestamps")
                pts = frame.pts * frame.time_base
                if first_pts is None:
                    first_pts = pts
                timestamp = round(float(pts - first_pts) * 1000)
                if timestamp < previous_ms or frame.width * frame.height > 3840 * 2160:
                    raise ValueError("Invalid video frame metadata")
                previous_ms = timestamp
                yield SourceFrame(
                    index, timestamp, frame.to_image() if index % sampling == 0 else None
                )


class Detector(Protocol):
    def detect(self, frame: SourceFrame) -> list[BoundingBoxPixels]: ...


@dataclass(frozen=True)
class CompletedTrack:
    key: str
    started_ms: int
    ended_ms: int
    representative: SourceFrame
    bbox: BoundingBoxPixels


class Tracker(Protocol):
    def update(
        self, frame: SourceFrame, boxes: list[BoundingBoxPixels]
    ) -> list[CompletedTrack]: ...
    def finish(self) -> list[CompletedTrack]: ...
    def close(self) -> None: ...


class Encoder(Protocol):
    def encode(self, crop: Image.Image) -> list[float]: ...


class DemoDetector:
    """Synthetic central box; deliberately NOT a person detector."""

    def detect(self, frame):
        width, height = frame.image.size
        return [
            BoundingBoxPixels(
                width // 4, height // 4, max(1, width // 2), max(1, height // 2), width, height
            )
        ]


class DemoTracker:
    """One synthetic track per five sampled frames; keeps only one representative."""

    def __init__(self):
        self.first = None
        self.count = 0
        self.last_ms = 0

    def update(self, frame, boxes):
        if not boxes:
            return []
        if self.first is None:
            self.first = (frame, boxes[0])
        self.last_ms = frame.timestamp_ms
        self.count += 1
        return self.finish() if self.count == 5 else []

    def finish(self):
        if self.first is None:
            return []
        frame, bbox = self.first
        result = CompletedTrack(str(frame.index), frame.timestamp_ms, self.last_ms, frame, bbox)
        self.close()
        return [result]

    def close(self):
        self.first, self.count, self.last_ms = None, 0, 0


class DemoEncoder:
    def encode(self, crop):
        digest = hashlib.sha256(crop.resize((16, 16)).tobytes()).digest()
        values = [float(digest[index % 32] + 1) for index in range(256)]
        norm = math.sqrt(sum(value * value for value in values))
        return [value / norm for value in values]


class Pipeline:
    def __init__(self, detector, tracker, encoder, manifest):
        self.detector, self.tracker, self.encoder, self.manifest = (
            detector,
            tracker,
            encoder,
            manifest,
        )

    @classmethod
    def demo(cls, config):
        if (
            config.detector_name != "demo_detector"
            or config.detector_version != "1"
            or config.tracker_version != "1"
            or config.tracker_name != "demo_tracker"
            or config.encoder_version != "fake_demo_v1"
            or config.encoder_dimension != 256
            or config.checkpoint_sha256 != "0" * 64
        ):
            raise ValueError("Demo worker requires the isolated demo model configuration")
        return cls(
            DemoDetector(),
            DemoTracker(),
            DemoEncoder(),
            EncoderManifest("fake_demo_v1", 256, "0" * 64),
        )

    def request(self, job, area_id, track):
        frame, box = track.representative, track.bbox
        crop = frame.image.crop((box.x, box.y, box.x + box.width, box.y + box.height))
        embedding = self.encoder.encode(crop)
        output = io.BytesIO()
        frame.image.save(output, format="JPEG", quality=90)
        # Deterministic UUIDv4-shaped identity makes crash replay safe for the same job/track.
        track_id = uuid.UUID(
            bytes=hashlib.sha256(f"{job.id}:{track.key}".encode()).digest()[:16], version=4
        )
        return TrackIngestionRequest(
            track_id=track_id,
            camera_id=job.camera_id,
            area_id=area_id,
            processing_job_id=job.id,
            ai_config_version_id=job.ai_config_version_id,
            timeline_origin_utc=job.timeline_origin_utc.astimezone(UTC),
            source_frame_index=frame.index,
            source_started_at_ms=track.started_ms,
            source_ended_at_ms=track.ended_ms,
            representative_frame_timestamp_ms=frame.timestamp_ms,
            bbox=box,
            frame_bytes=output.getvalue(),
            embedding=embedding,
            encoder=self.manifest,
        )
