"""Supervised sequential video worker (separate from Flask)."""

import argparse
import os
import signal
import subprocess
import sys
import threading

from dotenv import load_dotenv

from person_search.config import StorageSettings
from person_search.services.jobs import JobService
from person_search.services.track_ingestion import TrackIngestionService
from person_search.services.video_staging import VideoStaging
from person_search.storage.milvus.vectors import MilvusPersonTrackIndex
from person_search.storage.minio.frames import MinioFrameStore
from person_search.storage.postgres.unit_of_work import UnitOfWork
from person_search.storage.runtime import StorageRuntime
from person_search.workers.pipeline import Pipeline
from person_search.workers.runner import VideoWorker


def main():
    load_dotenv()
    parser = argparse.ArgumentParser(
        description="Sequential video worker; demo adapters are opt-in"
    )
    parser.add_argument("--once", action="store_true", help="Process at most one job")
    parser.add_argument("--demo", action="store_true", help="Use isolated synthetic demo pipeline")
    args = parser.parse_args()
    if not args.demo:
        parser.error("No production AI adapter is configured. Use --demo with the demo registry.")
    stopped = threading.Event()
    for name in (signal.SIGTERM, signal.SIGINT):
        signal.signal(name, lambda *_: stopped.set())
    if not args.once:
        # Hard deadline also terminates native decoders/model calls that do not return to Python.
        deadline = int(os.getenv("PERSON_SEARCH_JOB_TIMEOUT_SECONDS", "3600"))
        while not stopped.is_set():
            child = subprocess.Popen(
                [sys.executable, "-m", "person_search.workers.main", "--once", "--demo"]
            )
            elapsed = 0
            while child.poll() is None and not stopped.wait(1):
                elapsed += 1
                if elapsed >= deadline:
                    child.kill()
                    break
            if stopped.is_set() and child.poll() is None:
                child.terminate()
            try:
                child.wait(timeout=10)
            except subprocess.TimeoutExpired:
                child.kill()
                child.wait()
            stopped.wait(3)
        return 0
    runtime = StorageRuntime.from_settings(StorageSettings.from_environment())
    try:

        def factory():
            return UnitOfWork(runtime.postgres.session_factory)

        jobs = JobService(factory, VideoStaging.from_environment())

        def ingestion(config):
            vectors = MilvusPersonTrackIndex(
                runtime.milvus.client,
                encoder_version=config.encoder_version,
                dimension=config.encoder_dimension,
                alias="person_track_embeddings_demo",
            )
            vectors.ensure_collection()
            return TrackIngestionService(
                factory,
                MinioFrameStore(runtime.minio.client, runtime.settings.minio.bucket),
                vectors,
            )

        worker = VideoWorker(
            runtime.postgres.engine, jobs, Pipeline.demo, ingestion, stop=stopped.is_set
        )
        worker.run_once()
    finally:
        runtime.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
