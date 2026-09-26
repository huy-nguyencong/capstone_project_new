import os
import shutil
import subprocess
import threading
import time
import uuid
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest

from person_search.services.camera_runtime import CameraRuntime
from person_search.storage.postgres.models import JobSourceType, JobStatus
from person_search.workers.durable import (
    BudgetedSource,
    SequentialProductionWorker,
    rtsp_source_factory,
)
from person_search.workers.production import ProductionPipelineResult
from person_search.workers.sources import RtspFrameSource

PUBLISH_URL = os.getenv("PERSON_SEARCH_RTSP_TEST_PUBLISH_URL")
READ_URL = os.getenv("PERSON_SEARCH_RTSP_TEST_READ_URL")

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        not (PUBLISH_URL and READ_URL and os.getenv("PERSON_SEARCH_RTSP_NETWORKS")),
        reason="requires MediaMTX, PERSON_SEARCH_RTSP_TEST_PUBLISH_URL/READ_URL and networks",
    ),
    pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="requires ffmpeg"),
]


class Publisher:
    def __init__(self, url: str) -> None:
        self.url = url
        self.process = None

    def start(self) -> None:
        self.process = subprocess.Popen(
            [
                "ffmpeg",
                "-v",
                "error",
                "-re",
                "-f",
                "lavfi",
                "-i",
                "testsrc2=size=320x240:rate=15",
                "-c:v",
                "libx264",
                "-preset",
                "ultrafast",
                "-tune",
                "zerolatency",
                "-g",
                "15",
                "-rtsp_transport",
                "tcp",
                "-f",
                "rtsp",
                self.url,
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        time.sleep(2)

    def stop(self) -> None:
        if self.process is not None and self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait()


@pytest.fixture
def publisher():
    stream = Publisher(PUBLISH_URL)
    stream.start()
    yield stream
    stream.stop()


def source(**options):
    runtime = CameraRuntime.from_environment()
    return RtspFrameSource(
        access_resolver=runtime.connection_url,
        connect_timeout=5,
        read_timeout=5,
        **options,
    ).open(READ_URL, camera_id=uuid.uuid4())


def test_happy_path_reads_monotonic_frames_from_mediamtx(publisher):
    with source(max_reconnects=0) as stream:
        frames = []
        for frame in stream:
            frames.append((frame.source_frame_index, frame.source_timestamp_ms, frame.width))
            frame.image.close()
            if len(frames) == 30:
                break
    assert [item[0] for item in frames] == list(range(30))
    assert all(left[1] <= right[1] for left, right in zip(frames, frames[1:], strict=False))
    assert {item[2] for item in frames} == {320}


def test_publisher_restart_reconnects_and_keeps_timeline_monotonic(publisher):
    restarted = threading.Event()

    def restart():
        publisher.stop()
        time.sleep(1)
        publisher.start()
        restarted.set()

    with source(max_reconnects=10, backoff_seconds=0.5, max_backoff_seconds=2) as stream:
        indices, stamps = [], []
        for frame in stream:
            indices.append(frame.source_frame_index)
            stamps.append(frame.source_timestamp_ms)
            frame.image.close()
            if len(indices) == 20:
                threading.Thread(target=restart, daemon=True).start()
            if restarted.is_set() and len(indices) >= 60:
                break
        reconnects = stream.reconnects

    assert reconnects >= 1
    assert indices == list(range(len(indices)))
    assert all(left <= right for left, right in zip(stamps, stamps[1:], strict=False))
    assert max(b - a for a, b in zip(stamps, stamps[1:], strict=False)) >= 1000


def test_worker_consumes_budgeted_rtsp_job_through_shared_pipeline_contract(publisher):
    runtime = CameraRuntime.from_environment()
    factory = rtsp_source_factory(
        lambda camera_id: (READ_URL, None),
        runtime.connection_url,
        max_reconnects=2,
        connect_timeout=5,
        read_timeout=5,
    )
    job = SimpleNamespace(
        id=uuid.uuid4(),
        lease_token=uuid.uuid4(),
        camera_id=uuid.uuid4(),
        ai_config_version_id=uuid.uuid4(),
        source_type=JobSourceType.RTSP,
        source_ref=None,
        sampling_interval=5,
        timeline_origin_utc=datetime.now(UTC),
        attempts=1,
        total_frames=45,
    )
    finished = []
    seen = {}

    class Jobs:
        queue = [job]

        def cleanup(self):
            return None

        def claim(self):
            return self.queue.pop(0) if self.queue else None

        def checkpoint(self, *args, **kwargs):
            return True

        def finish(self, job_id, token, status, error_code=None):
            finished.append((status, error_code))

        def defer_retry(self, *args):
            return True

    class Pipeline:
        def run(self, frames):
            assert isinstance(frames, BudgetedSource)
            count = 0
            for frame in frames:
                frame.image.close()
                count += 1
            seen["frames"] = count
            return ProductionPipelineResult(count, count // 5, 0, 0, (), ())

    class Lock:
        def __enter__(self):
            return True

        def __exit__(self, *args):
            return None

    worker = SequentialProductionWorker(
        Jobs(),
        lock_factory=Lock,
        source_factory=factory,
        pipeline_factory=lambda snapshot, cancelled, progress: Pipeline(),
        result_consumer=lambda snapshot, result: None,
    )

    assert worker.run_once()
    assert finished == [(JobStatus.SUCCEEDED, None)]
    assert seen["frames"] == 45
