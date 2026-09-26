"""Production worker entrypoint with durable three-store track publication."""

from __future__ import annotations

import argparse
import os
import signal
import subprocess
import sys
import threading
from pathlib import Path

from dotenv import load_dotenv

from person_search.ai.preflight import apply_resource_environment, load_resource_settings
from person_search.ai.registry import RegistryMode, load_registry
from person_search.config import StorageSettings
from person_search.services.jobs import JobService
from person_search.services.track_ingestion import TrackIngestionService
from person_search.services.video_staging import VideoStaging
from person_search.storage.milvus.vectors import MilvusPersonTrackIndex
from person_search.storage.minio.frames import MinioFrameStore
from person_search.storage.postgres.models import AIConfigVersion, Camera
from person_search.storage.postgres.unit_of_work import UnitOfWork
from person_search.storage.runtime import StorageRuntime
from person_search.workers.durable import (
    PostgresWorkerLock,
    SequentialProductionWorker,
    staged_file_source_factory,
)
from person_search.workers.errors import AIErrorCode, AIWorkerError
from person_search.workers.production import build_production_pipeline
from person_search.workers.publication import ProductionTrackPublisher


class PublisherNotConfigured:
    """Compatibility fail-closed consumer used by focused orchestration tests."""

    def __call__(self, snapshot, result) -> None:
        del snapshot, result
        raise AIWorkerError(AIErrorCode.STORAGE_UNAVAILABLE)


def _required_path(name: str, default: Path | None = None) -> Path:
    raw = os.getenv(name) or (str(default) if default else "")
    path = Path(raw).resolve() if raw else None
    if path is None or not path.is_file():
        raise ValueError(f"{name} must reference an existing file.")
    return path


def build_worker(*, stopped, result_consumer=None):
    project_config = Path(__file__).parents[3] / "config"
    registry_path = _required_path("PERSON_SEARCH_MODEL_REGISTRY")
    artifact_root = Path(
        os.getenv("PERSON_SEARCH_MODEL_ARTIFACT_ROOT") or registry_path.parent
    ).resolve()
    preflight_ids = {"yolo11n_coco", "bytetrack_v1", "rasa_cuhk_pedes_v1"}
    registry = load_registry(
        registry_path,
        artifact_root=artifact_root,
        preflight_available=preflight_ids,
    )
    if registry.mode is not RegistryMode.PRODUCTION:
        raise ValueError("Production worker requires a production model registry.")
    resource_settings = load_resource_settings(
        os.getenv("PERSON_SEARCH_AI_RESOURCE_CONFIG")
        or project_config / "ai_resources.json",
        os.getenv("PERSON_SEARCH_AI_RESOURCE_PROFILE", "local_cpu"),
    )
    apply_resource_environment(resource_settings)
    device = (
        "cuda" if resource_settings.device_preference.value == "cuda" else "cpu"
    )
    storage = StorageRuntime.from_settings(StorageSettings.from_environment())
    staging = VideoStaging.from_environment()

    def unit_of_work():
        return UnitOfWork(storage.postgres.session_factory)

    jobs = JobService(unit_of_work, staging)

    def publish(snapshot, result):
        with unit_of_work() as work:
            config = work.session.get(AIConfigVersion, snapshot.ai_config_version_id)
            camera = work.session.get(Camera, snapshot.camera_id)
            if config is None or camera is None:
                raise ValueError("Job publication lineage no longer exists.")
            area_id = camera.area_id
            encoder_version = config.encoder_version
            encoder_dimension = config.encoder_dimension
        vectors = MilvusPersonTrackIndex(
            storage.milvus.client,
            encoder_version=encoder_version,
            dimension=encoder_dimension,
        )
        vectors.ensure_collection()
        ingestion = TrackIngestionService(
            unit_of_work,
            MinioFrameStore(storage.minio.client, storage.settings.minio.bucket),
            vectors,
        )
        ProductionTrackPublisher(ingestion, area_id, jobs)(snapshot, result)

    def pipeline_factory(snapshot, cancelled, progress):
        with unit_of_work() as work:
            config = work.session.get(AIConfigVersion, snapshot.ai_config_version_id)
            if config is None:
                raise ValueError("Job AI configuration no longer exists.")
            work.session.expunge(config)
        return build_production_pipeline(
            registry,
            config,
            artifact_root=artifact_root,
            detector_settings_path=_required_path(
                "PERSON_SEARCH_DETECTOR_CONFIG",
                project_config / "ultralytics_yolo_detector.json",
            ),
            selector_settings_path=_required_path(
                "PERSON_SEARCH_SELECTOR_CONFIG",
                project_config / "representative_selector.json",
            ),
            rasa_settings_path=_required_path(
                "PERSON_SEARCH_RASA_CONFIG",
                project_config / "rasa_cuhk_pedes_runtime.json",
            ),
            processing_job_id=snapshot.job_id,
            ai_config_version_id=snapshot.ai_config_version_id,
            sampling_interval=snapshot.sampling_interval,
            job_timeout_seconds=float(os.getenv("PERSON_SEARCH_JOB_TIMEOUT_SECONDS", "3600")),
            device=device,
            cancelled=cancelled,
            progress=progress,
        )

    worker = SequentialProductionWorker(
        jobs,
        lock_factory=lambda: PostgresWorkerLock(storage.postgres.engine),
        source_factory=staged_file_source_factory(
            staging,
            max_bytes=int(os.getenv("PERSON_SEARCH_VIDEO_MAX_BYTES", "524288000")),
        ),
        pipeline_factory=pipeline_factory,
        result_consumer=result_consumer or publish,
        stop=stopped,
    )
    return worker, storage


def _supervise_child(stopped: threading.Event, deadline: int) -> None:
    child = subprocess.Popen(
        [sys.executable, "-m", "person_search.workers.production_main", "--once"]
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


def main() -> int:
    load_dotenv()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--once", action="store_true")
    args = parser.parse_args()
    stopped = threading.Event()
    for name in (signal.SIGTERM, signal.SIGINT):
        signal.signal(name, lambda *_: stopped.set())
    if not args.once:
        deadline = int(os.getenv("PERSON_SEARCH_JOB_TIMEOUT_SECONDS", "3600"))
        while not stopped.is_set():
            _supervise_child(stopped, deadline)
            stopped.wait(3)
        return 0
    worker, storage = build_worker(stopped=stopped.is_set)
    try:
        worker.run_once()
    finally:
        storage.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
