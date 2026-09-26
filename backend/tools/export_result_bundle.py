from __future__ import annotations

import argparse
import json
import os
import time
import uuid
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

from person_search.ai.registry import load_registry
from person_search.evaluation.environment import environment_snapshot, file_sha256
from person_search.storage.postgres.models import JobSourceType
from person_search.workers.durable import JobExecutionSnapshot
from person_search.workers.production import build_production_pipeline
from person_search.workers.publication import BundlePublisher
from person_search.workers.sources import FileFrameSource

DETECTOR_ID = "yolo11n_coco"
TRACKER_ID = "bytetrack_v1"


def _config_path(config_root: Path, variable: str, name: str) -> Path:
    return Path(os.getenv(variable) or config_root / name)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Process one video offline (e.g. Colab T4) and export a result bundle."
    )
    parser.add_argument("--registry", type=Path, required=True)
    parser.add_argument("--artifact-root", type=Path, required=True)
    parser.add_argument("--config-root", type=Path, default=Path("config"))
    parser.add_argument("--video", type=Path, required=True)
    parser.add_argument("--camera-id", type=uuid.UUID, required=True)
    parser.add_argument("--area-id", type=uuid.UUID, required=True)
    parser.add_argument("--job-id", type=uuid.UUID, required=True)
    parser.add_argument("--config-id", type=uuid.UUID, required=True)
    parser.add_argument("--timeline-origin", required=True)
    parser.add_argument("--sampling-interval", type=int, default=10)
    parser.add_argument("--device", default="cpu")
    parser.add_argument("--max-bytes", type=int, default=2 * 1024**3)
    parser.add_argument("--job-timeout-seconds", type=float, default=6 * 3600.0)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    origin = datetime.fromisoformat(args.timeline_origin.replace("Z", "+00:00"))
    if origin.tzinfo is None:
        parser.error("--timeline-origin must include a timezone")
    if args.sampling_interval < 1:
        parser.error("--sampling-interval must be positive")

    registry = load_registry(
        args.registry,
        artifact_root=args.artifact_root,
        preflight_available={DETECTOR_ID, TRACKER_ID, "rasa_cuhk_pedes_v1"},
    )
    selection = registry.resolve(DETECTOR_ID, TRACKER_ID)
    config = SimpleNamespace(
        detector_name=selection.detector.id,
        detector_version=selection.detector.version,
        tracker_name=selection.tracker.id,
        tracker_version=selection.tracker.version,
        encoder_name=selection.encoder.id,
        encoder_version=selection.encoder.version,
        encoder_dimension=selection.encoder.dimension,
        checkpoint_sha256=selection.encoder.artifact.sha256,
    )
    snapshot = JobExecutionSnapshot(
        args.job_id,
        uuid.uuid4(),
        args.camera_id,
        args.config_id,
        JobSourceType.FILE,
        args.video.name,
        args.sampling_interval,
        origin,
        1,
    )
    pipeline = build_production_pipeline(
        registry,
        config,
        artifact_root=args.artifact_root,
        detector_settings_path=_config_path(
            args.config_root, "PERSON_SEARCH_DETECTOR_CONFIG", "ultralytics_yolo_detector.json"
        ),
        selector_settings_path=_config_path(
            args.config_root, "PERSON_SEARCH_SELECTOR_CONFIG", "representative_selector.json"
        ),
        rasa_settings_path=_config_path(
            args.config_root, "PERSON_SEARCH_RASA_CONFIG", "rasa_cuhk_pedes_runtime.json"
        ),
        processing_job_id=args.job_id,
        ai_config_version_id=args.config_id,
        sampling_interval=args.sampling_interval,
        job_timeout_seconds=args.job_timeout_seconds,
        device=args.device,
    )
    started = time.perf_counter()
    source = FileFrameSource(max_bytes=args.max_bytes).open(args.video, camera_id=args.camera_id)
    with source:
        result = pipeline.run(source)
    elapsed = time.perf_counter() - started
    args.output.parent.mkdir(parents=True, exist_ok=True)
    try:
        BundlePublisher().write(args.output, snapshot, args.area_id, result)
    finally:
        images = {
            id(item.track.representative.frame.image): item.track.representative.frame.image
            for item in result.encoded_tracks
        }
        for image in images.values():
            image.close()
    sidecar = args.output.with_suffix(".lineage.json")
    sidecar.write_text(
        json.dumps(
            {
                "bundle_sha256": file_sha256(args.output),
                "video": {"name": args.video.name, "sha256": file_sha256(args.video)},
                "sampling_interval": args.sampling_interval,
                "source_frames": result.source_frames,
                "sampled_frames": result.sampled_frames,
                "tracks": len(result.encoded_tracks),
                "elapsed_seconds": round(elapsed, 3),
                "timings": [
                    {"stage": item.stage, "calls": item.calls, "elapsed_ms": item.elapsed_ms}
                    for item in result.timings
                ],
                "environment": environment_snapshot(extra={"device": args.device}),
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    print(json.dumps({"bundle": str(args.output), "lineage": str(sidecar)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
