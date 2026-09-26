from __future__ import annotations

import hashlib
import json
import uuid
from pathlib import Path

import pytest
from PIL import Image

from person_search.ai.registry import (
    ArtifactReference,
    DeviceKind,
    Provenance,
    TrackerEntry,
)
from person_search.ai.trackers import (
    ByteTrackPersonTracker,
    ByteTrackSettings,
    RawTrack,
    UltralyticsByteTrackBackend,
    build_bytetrack,
    load_bytetrack_settings,
)
from person_search.storage.contracts import BoundingBoxPixels
from person_search.workers.contracts import (
    Detection,
    ModelLineage,
    SampledFrame,
    SourceFrame,
    TrackState,
)
from person_search.workers.errors import AIErrorCode, AIWorkerError

pytestmark = pytest.mark.unit


class FakeBackend:
    def __init__(self, batches=(), *, error=None):
        self.batches = iter(batches)
        self.error = error
        self.opened = 0
        self.closed = 0

    def open(self):
        self.opened += 1

    def update(self, detections):
        if self.error:
            raise self.error
        return next(self.batches, ())

    def close(self):
        self.closed += 1


def sample(sequence: int, camera_id=None, *, interval=10) -> SampledFrame:
    source = SourceFrame(
        camera_id or uuid.uuid4(),
        sequence * interval,
        sequence * 400,
        Image.new("RGB", (100, 80), "navy"),
        100,
        80,
    )
    return SampledFrame(source, interval, sequence)


def detection(frame: SampledFrame, x=10) -> Detection:
    return Detection(
        BoundingBoxPixels(x, 10, 20, 40, frame.width, frame.height),
        0,
        "person",
        0.9,
        ModelLineage("yolo", "1", "a" * 64),
    )


def tracker(backend, **settings) -> ByteTrackPersonTracker:
    return ByteTrackPersonTracker(
        backend,
        lineage=ModelLineage("bytetrack", "1", "b" * 64),
        settings=ByteTrackSettings(**settings),
    )


def test_confirmation_active_updates_and_eof_flush() -> None:
    camera_id = uuid.uuid4()
    backend = FakeBackend(
        [
            [RawTrack(1, 10, 10, 30, 50, 0)],
            [RawTrack(1, 12, 10, 32, 50, 0)],
        ]
    )
    subject = tracker(backend, minimum_confirmed_samples=2)
    first, second = sample(0, camera_id), sample(1, camera_id)
    subject.open()

    assert subject.update(first, [detection(first)]) == ()
    active = subject.update(second, [detection(second, 12)])
    ended = subject.flush()

    assert len(active) == len(ended) == 1
    assert active[0].local_track_id == "bt-1"
    assert active[0].state is TrackState.ACTIVE
    assert ended[0].state is TrackState.ENDED
    assert ended[0].source_timestamp_ms == second.source_timestamp_ms


def test_short_occlusion_preserves_track_and_timeout_ends_at_last_seen() -> None:
    camera_id = uuid.uuid4()
    backend = FakeBackend(
        [
            [RawTrack(7, 10, 10, 30, 50, 0)],
            [RawTrack(7, 11, 10, 31, 50, 0)],
            [],
            [],
            [RawTrack(7, 13, 10, 33, 50, 0)],
            [],
            [],
            [],
        ]
    )
    subject = tracker(
        backend,
        minimum_confirmed_samples=2,
        maximum_lost_samples=2,
        maximum_lost_milliseconds=1000,
    )
    subject.open()
    frames = [sample(index, camera_id) for index in range(8)]
    subject.update(frames[0], [detection(frames[0])])
    subject.update(frames[1], [detection(frames[1])])

    assert subject.update(frames[2], []) == ()
    assert subject.update(frames[3], []) == ()
    assert subject.update(frames[4], [detection(frames[4])])[0].state is TrackState.ACTIVE
    assert subject.update(frames[5], []) == ()
    assert subject.update(frames[6], []) == ()
    ended = subject.update(frames[7], [])
    assert len(ended) == 1 and ended[0].state is TrackState.ENDED
    assert ended[0].source_timestamp_ms == frames[4].source_timestamp_ms


def test_camera_and_timeline_cannot_cross_one_tracker_instance() -> None:
    camera_id = uuid.uuid4()
    subject = tracker(FakeBackend([[], []]))
    subject.open()
    subject.update(sample(0, camera_id), [])

    with pytest.raises(ValueError, match="camera/job"):
        subject.update(sample(1, uuid.uuid4()), [])
    with pytest.raises(ValueError, match="increase strictly"):
        subject.update(sample(0, camera_id), [])


def test_close_is_cancel_semantics_and_does_not_flush_completed_track() -> None:
    frame = sample(0)
    backend = FakeBackend([[RawTrack(1, 10, 10, 30, 50, 0)]])
    subject = tracker(backend, minimum_confirmed_samples=1)
    subject.open()
    assert subject.update(frame, [detection(frame)])

    subject.close()
    subject.close()

    assert backend.closed == 1
    with pytest.raises(RuntimeError, match="before flush"):
        subject.flush()


@pytest.mark.parametrize(
    "row",
    [
        RawTrack(0, 1, 1, 2, 2, 0),
        RawTrack(1, 1, 1, 2, 2, 3),
        RawTrack(1, float("nan"), 1, 2, 2, 0),
        RawTrack(1, 5, 5, 4, 4, 0),
    ],
)
def test_invalid_backend_output_fails_closed(row) -> None:
    frame = sample(0)
    backend = FakeBackend([[row]])
    subject = tracker(backend)
    subject.open()

    with pytest.raises(AIWorkerError) as caught:
        subject.update(frame, [detection(frame)])

    assert caught.value.code is AIErrorCode.TRACKER_OUTPUT_INVALID
    assert backend.closed == 1


def test_backend_failure_is_sanitized_and_closes_tracker() -> None:
    subject = tracker(FakeBackend(error=RuntimeError("private tracker detail")))
    subject.open()

    with pytest.raises(AIWorkerError) as caught:
        subject.update(sample(0), [])

    assert caught.value.code is AIErrorCode.TRACKER_INFERENCE_FAILED
    assert "private tracker detail" not in str(caught.value)


def test_settings_loader_is_strict(tmp_path: Path) -> None:
    path = tmp_path / "tracker.json"
    path.write_text(
        json.dumps(
            {
                "schema_version": "bytetrack-tracker/v1",
                "track_high_threshold": 0.25,
                "track_low_threshold": 0.1,
                "new_track_threshold": 0.25,
                "match_threshold": 0.8,
                "fuse_score": True,
                "minimum_confirmed_samples": 2,
                "maximum_lost_samples": 3,
                "maximum_lost_milliseconds": 2000,
            }
        ),
        encoding="utf-8",
    )
    assert load_bytetrack_settings(path).maximum_lost_samples == 3
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["unknown"] = True
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match="missing or unknown"):
        load_bytetrack_settings(path)


def test_factory_verifies_registry_artifact_and_checksum(tmp_path: Path) -> None:
    artifact = tmp_path / "tracker.json"
    source = Path(__file__).parents[2] / "config" / "bytetrack_tracker.json"
    artifact.write_bytes(source.read_bytes())
    digest = hashlib.sha256(artifact.read_bytes()).hexdigest()
    entry = TrackerEntry(
        "bytetrack_v1",
        "ByteTrack",
        "1",
        "test",
        "bytetrack",
        ArtifactReference("tracker.json", digest),
        (DeviceKind.CPU,),
        (6,),
        Provenance(
            "ultralytics",
            "8.4.163",
            "https://example.test",
            None,
            "AGPL-3.0",
            True,
            "approved",
        ),
        True,
        (),
        ("yolo11n_coco",),
    )
    backend = FakeBackend()

    built = build_bytetrack(entry, artifact_root=tmp_path, backend_factory=lambda _: backend)
    built.open()
    assert backend.opened == 1
    artifact.write_text("changed", encoding="utf-8")
    with pytest.raises(ValueError, match="checksum changed"):
        build_bytetrack(entry, artifact_root=tmp_path)


def test_real_backend_tracks_multiple_people_and_resets_between_jobs() -> None:
    camera_id = uuid.uuid4()
    subject = tracker(UltralyticsByteTrackBackend(ByteTrackSettings()))
    subject.open()
    active_sets = []
    for sequence, positions in enumerate(((10, 65), (14, 61), (18, 57))):
        frame = sample(sequence, camera_id)
        updates = subject.update(frame, [detection(frame, x) for x in positions])
        if updates:
            active_sets.append({item.local_track_id for item in updates})
    subject.close()

    assert active_sets == [{"bt-1", "bt-2"}, {"bt-1", "bt-2"}]

    next_frame = sample(0, uuid.uuid4())
    next_job = tracker(
        UltralyticsByteTrackBackend(ByteTrackSettings()),
        minimum_confirmed_samples=1,
    )
    next_job.open()
    updates = next_job.update(next_frame, [detection(next_frame)])
    next_job.close()
    assert updates[0].local_track_id == "bt-1"
