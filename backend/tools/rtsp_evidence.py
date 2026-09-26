from __future__ import annotations

import argparse
import json
import threading
import time
import uuid
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import func, select

from person_search.evaluation.environment import environment_snapshot
from person_search.observability import configure_logging, redact_text
from person_search.services.jobs import JobService
from person_search.services.video_staging import VideoStaging
from person_search.storage.postgres.models import (
    Camera,
    JobSourceType,
    JobStatus,
    PersonTrack,
    ProcessingJob,
    TrackIndexStatus,
)
from person_search.storage.postgres.unit_of_work import UnitOfWork


def _search(storage, text: str, operator_id: uuid.UUID, top_k: int) -> dict:
    import os

    from person_search.ai.config_loader import ProductionComponentFactory
    from person_search.services.cameras import CameraService
    from person_search.services.query_encoder import InProcessQueryEncoder
    from person_search.services.searches import SearchService

    registry = CameraService.registry_from_environment("production")
    components = ProductionComponentFactory.from_environment(
        artifact_root=registry.artifact_root,
        config_root=Path(os.getenv("PERSON_SEARCH_CONFIG_ROOT", "config")),
    )
    encoder = InProcessQueryEncoder(registry, components.query_gateway)
    try:
        service = SearchService(
            lambda: UnitOfWork(storage.postgres.session_factory),
            storage.milvus.client,
            encoder=encoder,
        )
        started = time.perf_counter()
        response = service.search_text(operator_id, text, top_k=top_k)
        latency = (time.perf_counter() - started) * 1000
    finally:
        encoder.close()
    return {
        "query": text,
        "latency_ms": round(latency, 1),
        "results": [
            {
                "track_id": str(item.track_id),
                "camera_id": str(item.camera_id),
                "matching_score": round(item.matching_score, 6),
                "appeared_at": item.appeared_at_utc.isoformat(),
            }
            for item in response.results
        ],
    }


def main() -> int:
    load_dotenv()
    configure_logging()
    parser = argparse.ArgumentParser(
        description="Run one bounded RTSP session through the production worker as evidence."
    )
    parser.add_argument("--camera-id", type=uuid.UUID, required=True)
    parser.add_argument("--frames", type=int, default=1800)
    parser.add_argument("--sampling-profile")
    parser.add_argument("--actor-user-id", type=uuid.UUID)
    parser.add_argument("--search-text")
    parser.add_argument("--operator-user-id", type=uuid.UUID)
    parser.add_argument("--top-k", type=int, default=8)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.search_text and args.operator_user_id is None:
        parser.error("--search-text requires --operator-user-id")

    from person_search.workers.production_main import build_worker

    captured = {}
    stopped = threading.Event()
    worker, storage = build_worker(
        stopped=stopped.is_set,
        source_hook=lambda snapshot, source: captured.update(source=source, job=snapshot.job_id),
    )

    def unit_of_work():
        return UnitOfWork(storage.postgres.session_factory)

    try:
        with unit_of_work() as work:
            busy = work.session.scalar(
                select(func.count())
                .select_from(ProcessingJob)
                .where(ProcessingJob.status.in_((JobStatus.PENDING, JobStatus.RUNNING)))
            )
            camera = work.session.get(Camera, args.camera_id)
            public_url = camera.rtsp_url if camera is not None else None
        if busy:
            parser.error("Other PENDING/RUNNING jobs exist; finish them first.")
        jobs = JobService(
            unit_of_work,
            VideoStaging.from_environment(),
            source_types=(JobSourceType.FILE, JobSourceType.RTSP),
        )
        created = jobs.create_rtsp_job(
            args.camera_id,
            args.actor_user_id,
            max_source_frames=args.frames,
            sampling_profile=args.sampling_profile,
        )
        started = time.perf_counter()
        processed = worker.run_once()
        elapsed = time.perf_counter() - started
        job = jobs.get(created["id"])
        with unit_of_work() as work:
            ready = work.session.scalar(
                select(func.count())
                .select_from(PersonTrack)
                .where(
                    PersonTrack.processing_job_id == uuid.UUID(created["id"]),
                    PersonTrack.index_status == TrackIndexStatus.READY,
                )
            )
        source = captured.get("source")
        report = {
            "schema": "person-search-rtsp-evidence/v1",
            "camera": {
                "id": str(args.camera_id),
                "rtsp_url": redact_text(public_url or ""),
            },
            "processed_created_job": processed and captured.get("job") == uuid.UUID(created["id"]),
            "wall_seconds": round(elapsed, 3),
            "reconnects": source.reconnects if source is not None else None,
            "job": {
                key: job.get(key)
                for key in (
                    "id",
                    "source_type",
                    "status",
                    "error_code",
                    "processed_frames",
                    "sampled_frames",
                    "sampling_interval",
                    "completed_tracks",
                    "published_tracks",
                    "tracks_ready",
                    "metrics",
                    "recorded_started_at",
                    "started_at",
                    "ended_at",
                )
            },
            "tracks_ready": ready,
            "environment": environment_snapshot(),
        }
        if args.search_text and job.get("status") == "SUCCEEDED":
            report["search"] = _search(
                storage, args.search_text, args.operator_user_id, args.top_k
            )
    finally:
        storage.close()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({"output": str(args.output), "job": report["job"]["status"]}))
    return 0 if report["job"]["status"] == "SUCCEEDED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
