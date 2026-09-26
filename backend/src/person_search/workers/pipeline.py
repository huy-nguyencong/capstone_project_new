"""Frame source and replaceable detector/tracker/encoder interfaces for BE-10."""

import hashlib
import io
import uuid
from datetime import UTC

from person_search.storage.contracts import TrackIngestionRequest
from person_search.workers.sources import FileFrameSource


class VideoFrameSource:
    """Compatibility facade while the worker migrates to the FrameSource lifecycle."""

    def __init__(self, **source_options):
        self.source_options = source_options

    def frames(self, source, sampling, camera_id):
        del sampling  # Sampling remains a downstream concern until AIW-08.
        opened = FileFrameSource(**self.source_options).open(source, camera_id=camera_id)
        with opened:
            yield from opened


class Pipeline:
    request_type = TrackIngestionRequest

    def __init__(self, detector, tracker, encoder, manifest):
        self.detector, self.tracker, self.encoder, self.manifest = (
            detector,
            tracker,
            encoder,
            manifest,
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
        return self.request_type(
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
