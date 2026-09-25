import hashlib
import io
import os
import subprocess
import uuid
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest
from sqlalchemy import select, text
from test_camera_admin import client, create_camera
from test_camera_admin import world as world

from person_search.services.jobs import JobService
from person_search.services.track_ingestion import TrackIngestionService
from person_search.services.video_staging import VideoStaging
from person_search.storage.contracts import frame_object_key
from person_search.storage.minio.frames import FrameInfo
from person_search.storage.postgres.models import JobStatus, PersonTrack, ProcessingJob, UserRole
from person_search.storage.postgres.unit_of_work import UnitOfWork
from person_search.workers.pipeline import Pipeline, VideoFrameSource
from person_search.workers.runner import WORKER_LOCK, VideoWorker

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        not os.getenv("PERSON_SEARCH_CAMERA_TEST_DSN"), reason="requires disposable database"
    ),
]

@pytest.fixture
def video(tmp_path):
    path = tmp_path / "fixture.mp4"
    subprocess.run(
        [
            "ffmpeg",
            "-v",
            "error",
            "-f",
            "lavfi",
            "-i",
            "color=c=red:s=64x48:r=25",
            "-t",
            "2.4",
            "-c:v",
            "mpeg4",
            str(path),
        ],
        check=True,
        timeout=15,
    )
    return path.read_bytes()


@pytest.fixture
def setup(world, tmp_path):
    app, cameras, users, area, factory = world
    cameras.configure(
        {
            "detector_id": "demo_detector",
            "tracker_id": "demo_tracker",
            "version": cameras.config()["version"],
        },
        users[UserRole.ADMIN].id,
    )
    jobs = JobService(
        lambda: UnitOfWork(factory), VideoStaging(tmp_path / "private", reserve_bytes=0)
    )
    app.extensions["person_search.dependencies"].register("jobs.service", jobs)
    api = client(world)
    camera = create_camera(api, area).json
    api.put(f"/api/v1/admin/cameras/{camera['id']}/ai-state", json={"enabled": True})
    yield SimpleNamespace(world=world, api=api, jobs=jobs, camera=camera, factory=factory)
    with factory() as session:
        for job in session.scalars(
            select(ProcessingJob).where(ProcessingJob.camera_id == uuid.UUID(camera["id"]))
        ):
            job.status = JobStatus.CANCELLED
        session.commit()
    jobs.cleanup()


def upload(setup, video, key=None, sampling=10):
    return setup.api.post(
        f"/api/v1/admin/cameras/{setup.camera['id']}/processing-jobs",
        headers={"Idempotency-Key": key or str(uuid.uuid4())},
        data={
            "file": (io.BytesIO(video), "clip.mp4"),
            "recorded_started_at": "2026-09-25T08:00:00+07:00",
            "sampling_interval": str(sampling),
        },
    )


class MemoryFrames:
    def __init__(self):
        self.values = {}

    def put_frame(self, **values):
        key = frame_object_key(values["camera_id"], values["captured_at"], values["track_id"])
        info = FrameInfo(
            key, hashlib.sha256(values["data"]).hexdigest(), len(values["data"]), "image/jpeg"
        )
        self.values[key] = info
        return info

    def head_frame(self, key):
        return self.values[key]


class MemoryVectors:
    encoder_version = "fake_demo_v1"

    def __init__(self):
        self.values = {}

    def upsert(self, **values):
        self.values[values["track_id"]] = {
            "track_id": str(values["track_id"]),
            "area_id": str(values["area_id"]),
            "camera_id": str(values["camera_id"]),
            "encoder_version": self.encoder_version,
            "index_status": "READY",
        }

    def get(self, key):
        return self.values.get(key)


def worker(setup, **kwargs):
    frames, vectors = MemoryFrames(), MemoryVectors()
    ingestion = TrackIngestionService(setup.jobs.factory, frames, vectors)
    return VideoWorker(
        setup.factory.kw["bind"], setup.jobs, Pipeline.demo, lambda _: ingestion, **kwargs
    )


def test_upload_idempotency_validation_permissions_and_cancel(setup, video):
    key = str(uuid.uuid4())
    created = upload(setup, video, key)
    assert created.status_code == 202, created.json
    job = created.json
    assert job["status"] == "PENDING" and job["processed_frames"] == 0
    assert "source_ref" not in job and "lease_token" not in job
    assert upload(setup, video, key).json["id"] == job["id"]
    assert upload(setup, video, key, sampling=20).status_code == 409
    assert len(list(setup.jobs.staging.root.iterdir())) == 1
    assert upload(setup, b"fake video").status_code == 415
    path = f"/api/v1/admin/processing-jobs/{job['id']}"
    for role in (UserRole.OPERATOR, UserRole.VIEWER):
        api = client(setup.world, role)
        for method, endpoint in [
            ("GET", path),
            ("POST", path + "/cancel"),
            ("GET", "/api/v1/admin/processing-jobs"),
            ("POST", f"/api/v1/admin/cameras/{setup.camera['id']}/processing-jobs"),
        ]:
            assert api.open(endpoint, method=method).status_code == 403
    anonymous = setup.world[0].test_client()
    assert anonymous.get(path).status_code == 401
    admin = client(setup.world)
    admin.environ_base.pop("HTTP_X_CSRF_TOKEN")
    assert admin.post(path + "/cancel").status_code == 403
    assert setup.api.post(path + "/cancel").json["status"] == "CANCELLED"
    assert setup.api.post(path + "/cancel").json["status"] == "CANCELLED"
    assert list(setup.jobs.staging.root.iterdir()) == []
    assert setup.api.get(path).json["status"] == "CANCELLED"


@pytest.mark.parametrize("sampling,expected", [(10, 6), (20, 3)])
def test_real_video_through_fake_ai_reaches_ready(setup, video, sampling, expected):
    response = upload(setup, video, sampling=sampling)
    assert response.status_code == 202, response.json
    job_id = response.json["id"]
    assert worker(setup).run_once()
    job = setup.jobs.get(job_id)
    assert job["status"] == "SUCCEEDED", job
    assert job["processed_frames"] == job["total_frames"] == 60
    assert job["sampled_frames"] == expected
    assert job["tracks_ready"] == (2 if sampling == 10 else 1)
    assert not list(setup.jobs.staging.root.iterdir())
    with setup.factory() as session:
        tracks = list(
            session.scalars(
                select(PersonTrack).where(PersonTrack.processing_job_id == uuid.UUID(job_id))
            )
        )
        assert min(t.source_frame_index for t in tracks) == 0
        assert min(t.appeared_at_utc.astimezone(UTC) for t in tracks) == datetime(
            2026, 9, 25, 1, tzinfo=UTC
        )
        assert all(t.encoder_version == "fake_demo_v1" for t in tracks)


def test_worker_crash_replay_lock_and_cancel_running(setup, video):
    job_id = upload(setup, video).json["id"]
    engine = setup.factory.kw["bind"]
    with engine.connect() as guard:
        guard.execute(text("SELECT pg_advisory_lock(:key)"), {"key": WORKER_LOCK})
        assert not worker(setup).run_once()
        guard.execute(text("SELECT pg_advisory_unlock(:key)"), {"key": WORKER_LOCK})
    claimed = setup.jobs.claim()
    assert str(claimed.id) == job_id
    with setup.factory() as session:
        row = session.get(ProcessingJob, claimed.id)
        row.lease_expires_at = datetime.now(UTC) - timedelta(seconds=1)
        session.commit()
    assert worker(setup).run_once()
    assert setup.jobs.get(job_id)["status"] == "SUCCEEDED"
    second = upload(setup, video).json["id"]

    class CancelSource(VideoFrameSource):
        def frames(self, source, sampling, camera_id):
            for frame in super().frames(source, sampling, camera_id):
                if frame.index == 1:
                    setup.api.post(f"/api/v1/admin/processing-jobs/{second}/cancel")
                yield frame

    assert worker(setup, source=CancelSource()).run_once()
    assert setup.jobs.get(second)["status"] == "CANCELLED"
    assert not list(setup.jobs.staging.root.iterdir())


def test_crash_after_track_ingestion_replays_without_duplicates(setup, video):
    job_id = upload(setup, video).json["id"]

    class ProcessCrash(BaseException):
        pass

    class CrashingSource(VideoFrameSource):
        def frames(self, source, sampling, camera_id):
            for frame in super().frames(source, sampling, camera_id):
                if frame.index == 45:
                    raise ProcessCrash()
                yield frame

    running = worker(setup, source=CrashingSource())
    with pytest.raises(ProcessCrash):
        running.run_once()
    assert setup.jobs.get(job_id)["tracks_ready"] == 1
    assert setup.jobs.get(job_id)["status"] == "RUNNING"
    with setup.factory() as session:
        job = session.get(ProcessingJob, uuid.UUID(job_id))
        job.lease_expires_at = datetime.now(UTC) - timedelta(seconds=1)
        session.commit()
    running.source = VideoFrameSource()
    assert running.run_once()
    assert setup.jobs.get(job_id)["tracks_ready"] == 2
    assert setup.jobs.get(job_id)["status"] == "SUCCEEDED"


def test_disable_ai_and_component_failure_keep_sanitized_status(setup, video):
    job_id = upload(setup, video).json["id"]
    setup.api.put(f"/api/v1/admin/cameras/{setup.camera['id']}/ai-state", json={"enabled": False})
    assert worker(setup).run_once()
    assert setup.jobs.get(job_id)["status"] == "CANCELLED"
    assert upload(setup, video).status_code == 409
    setup.api.put(f"/api/v1/admin/cameras/{setup.camera['id']}/ai-state", json={"enabled": True})
    failed_id = upload(setup, video).json["id"]
    running = worker(setup)

    def broken(config):
        pipeline = Pipeline.demo(config)

        def detect(frame):
            raise RuntimeError("private path rtsp://admin:password@camera")

        pipeline.detector.detect = detect
        return pipeline

    running.pipeline_factory = broken
    assert running.run_once()
    result = setup.jobs.get(failed_id)
    assert result["status"] == "FAILED"
    assert result["error_code"] == "detector_failed"
    assert "password" not in str(result)
    assert not list(setup.jobs.staging.root.iterdir())


def test_graceful_stop_preserves_source_and_retry_limit_cleans_it(setup, video):
    job_id = upload(setup, video).json["id"]
    assert worker(setup, stop=lambda: True).run_once()
    assert setup.jobs.get(job_id)["status"] == "RUNNING"
    assert len(list(setup.jobs.staging.root.iterdir())) == 1
    with setup.factory() as session:
        job = session.get(ProcessingJob, uuid.UUID(job_id))
        job.attempts = 3
        job.lease_expires_at = datetime.now(UTC) - timedelta(seconds=1)
        session.commit()
    assert worker(setup).run_once()
    assert setup.jobs.get(job_id)["error_code"] == "worker_retries_exhausted"
    assert setup.jobs.get(job_id)["status"] == "FAILED"
    assert not list(setup.jobs.staging.root.iterdir())
