from __future__ import annotations

import io
import json
import math
import uuid
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest
from PIL import Image

from person_search.storage.contracts import BoundingBoxPixels, EncoderManifest
from person_search.storage.postgres.models import JobSourceType, TrackIndexStatus
from person_search.workers.contracts import (
    CompletedTrack,
    EmbeddingVector,
    ModelLineage,
    QualityComponent,
    QualityFlag,
    RepresentativeCandidate,
    SourceFrame,
)
from person_search.workers.durable import JobExecutionSnapshot
from person_search.workers.errors import AIErrorCode, AIWorkerError
from person_search.workers.production import EncodedTrack, ProductionPipelineResult
from person_search.workers.publication import (
    BundleImporter,
    BundlePublisher,
    BundleValidationError,
    ProductionTrackPublisher,
    ingestion_request,
    stable_track_id,
)

SHA = "a" * 64


def sample():
    job_id, camera_id, config_id = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    lineage = ModelLineage("encoder", "test_encoder_v1", SHA)
    frame = SourceFrame(camera_id, 10, 1000, Image.new("RGB", (20, 12), "red"), 20, 12)
    representative = RepresentativeCandidate(
        frame,
        BoundingBoxPixels(2, 1, 8, 10, 20, 12),
        (QualityComponent("sharpness", 1.0),),
        1.0,
    )
    track = CompletedTrack(
        camera_id,
        job_id,
        config_id,
        "local-7",
        900,
        1100,
        representative,
        QualityFlag.ACCEPTED,
        10,
        ModelLineage("yolo", "1", "b" * 64),
        ModelLineage("byte", "1", "c" * 64),
        lineage,
    )
    values = (1 / math.sqrt(2), 1 / math.sqrt(2))
    encoded = EncodedTrack(track, EmbeddingVector(values, 2, True, lineage))
    snapshot = JobExecutionSnapshot(
        job_id,
        uuid.uuid4(),
        camera_id,
        config_id,
        JobSourceType.FILE,
        "staged.mp4",
        10,
        datetime(2026, 1, 1, tzinfo=UTC),
        1,
    )
    result = ProductionPipelineResult(20, 2, 1, 1, (encoded,), ())
    return snapshot, result, uuid.uuid4()


class CapturingIngestion:
    def __init__(self, status=TrackIndexStatus.READY):
        self.status = status
        self.requests = []

    def ingest_track(self, request, *, correlation_id=None):
        self.requests.append(request)
        return SimpleNamespace(status=self.status)


class Jobs:
    def __init__(self):
        self.calls = []

    def checkpoint(self, *args):
        self.calls.append(args)
        return True


@pytest.mark.unit
def test_request_uses_retry_stable_id_and_complete_full_frame():
    snapshot, result, area_id = sample()
    first = ingestion_request(snapshot, area_id, result.encoded_tracks[0])
    second = ingestion_request(snapshot, area_id, result.encoded_tracks[0])
    assert first.track_id == second.track_id == stable_track_id(snapshot.job_id, "local-7")
    with Image.open(io.BytesIO(first.frame_bytes)) as stored:
        assert stored.size == (20, 12)
    assert first.bbox.width == 8
    result.encoded_tracks[0].track.representative.frame.image.close()


@pytest.mark.unit
def test_publisher_checkpoints_only_after_ready():
    snapshot, result, area_id = sample()
    ingestion, jobs = CapturingIngestion(), Jobs()
    ProductionTrackPublisher(ingestion, area_id, jobs)(snapshot, result)
    assert len(ingestion.requests) == 1
    assert jobs.calls[0][-2:] == (1, 1)
    result.encoded_tracks[0].track.representative.frame.image.close()


@pytest.mark.unit
def test_publisher_rejects_partial_track_without_advancing_progress():
    snapshot, result, area_id = sample()
    jobs = Jobs()
    with pytest.raises(AIWorkerError) as raised:
        ProductionTrackPublisher(CapturingIngestion(TrackIndexStatus.PENDING), area_id, jobs)(
            snapshot, result
        )
    assert raised.value.code is AIErrorCode.STORAGE_PUBLISH_FAILED
    assert jobs.calls == []
    result.encoded_tracks[0].track.representative.frame.image.close()


@pytest.mark.unit
def test_bundle_round_trip_and_checksum_rejection(tmp_path):
    snapshot, result, area_id = sample()
    path = tmp_path / "bundle.json"
    BundlePublisher().write(path, snapshot, area_id, result)
    ingestion = CapturingIngestion()
    encoder = EncoderManifest("test_encoder_v1", 2, SHA)
    importer = BundleImporter(ingestion, snapshot.ai_config_version_id, encoder)
    assert importer.import_file(path) == 1
    assert importer.import_file(path) == 1

    document = json.loads(path.read_text(encoding="utf-8"))
    document["tracks"][0]["frame_sha256"] = "0" * 64
    path.write_text(json.dumps(document), encoding="utf-8")
    with pytest.raises(BundleValidationError, match="checksum"):
        importer.import_file(path)
    result.encoded_tracks[0].track.representative.frame.image.close()
