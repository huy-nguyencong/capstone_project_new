from __future__ import annotations

import argparse
import json
import os
import uuid
from functools import partial
from pathlib import Path
from types import SimpleNamespace

from person_search.ai.registry import load_registry
from person_search.evaluation.benchmark import (
    REPORT_SCHEMA,
    LimitedSource,
    measure_run,
    measurements_as_dicts,
    run_benchmark,
    summarize,
)
from person_search.evaluation.environment import (
    environment_snapshot,
    file_sha256,
    registry_lineage,
)
from person_search.workers.production import build_production_pipeline
from person_search.workers.sources import FileFrameSource

DETECTOR_ID = "yolo11n_coco"
TRACKER_ID = "bytetrack_v1"


def _intervals(value: str) -> list[int]:
    items = [int(item) for item in value.split(",") if item.strip()]
    if not items or any(item < 1 for item in items):
        raise argparse.ArgumentTypeError("intervals must be positive integers")
    return items


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Benchmark sampling intervals with production adapters on real videos."
    )
    parser.add_argument("--registry", type=Path, required=True)
    parser.add_argument("--artifact-root", type=Path, required=True)
    parser.add_argument("--config-root", type=Path, default=Path("config"))
    parser.add_argument("--video", type=Path, action="append", required=True)
    parser.add_argument("--intervals", type=_intervals, default=[10, 20])
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--max-source-frames", type=int)
    parser.add_argument("--device", default="cpu")
    parser.add_argument("--profile", required=True)
    parser.add_argument("--max-bytes", type=int, default=2 * 1024**3)
    parser.add_argument("--job-timeout-seconds", type=float, default=6 * 3600.0)
    parser.add_argument("--short-track-ms", type=int, default=2000)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.repeats < 1:
        parser.error("--repeats must be positive")
    if 10 not in args.intervals:
        parser.error("--intervals must include the N=10 baseline")

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
    videos = {path.name: path.resolve() for path in args.video}
    camera_id = uuid.uuid4()

    def config_path(variable: str, name: str) -> Path:
        return Path(os.getenv(variable) or args.config_root / name)

    def pipeline_factory(interval: int):
        return build_production_pipeline(
            registry,
            config,
            artifact_root=args.artifact_root,
            detector_settings_path=config_path(
                "PERSON_SEARCH_DETECTOR_CONFIG", "ultralytics_yolo_detector.json"
            ),
            selector_settings_path=config_path(
                "PERSON_SEARCH_SELECTOR_CONFIG", "representative_selector.json"
            ),
            rasa_settings_path=config_path(
                "PERSON_SEARCH_RASA_CONFIG", "rasa_cuhk_pedes_runtime.json"
            ),
            processing_job_id=uuid.uuid4(),
            ai_config_version_id=uuid.uuid4(),
            sampling_interval=interval,
            job_timeout_seconds=args.job_timeout_seconds,
            device=args.device,
        )

    def source_factory(video: str):
        opened = FileFrameSource(max_bytes=args.max_bytes).open(videos[video], camera_id=camera_id)
        return LimitedSource(opened, args.max_source_frames)

    def measure(*, video: str, sampling_interval: int, repeat: int, cold: bool):
        measurement = measure_run(
            video=video,
            sampling_interval=sampling_interval,
            repeat=repeat,
            cold=cold,
            pipeline_factory=pipeline_factory,
            source_factory=partial(source_factory, video),
            short_track_ms=args.short_track_ms,
        )
        print(
            json.dumps(
                {
                    "video": video,
                    "N": sampling_interval,
                    "repeat": repeat,
                    "wall_seconds": measurement.wall_seconds,
                    "tracks": measurement.tracks,
                    "error": measurement.error,
                }
            ),
            flush=True,
        )
        return measurement

    measurements = run_benchmark(list(videos), args.intervals, args.repeats, measure)
    report = {
        "schema": REPORT_SCHEMA,
        "profile": args.profile,
        "settings": {
            "intervals": args.intervals,
            "repeats": args.repeats,
            "max_source_frames": args.max_source_frames,
            "device": args.device,
            "short_track_ms": args.short_track_ms,
            "order": "for each video: repeat -> interval; first run is cold",
        },
        "videos": {name: {"sha256": file_sha256(path)} for name, path in videos.items()},
        "models": registry_lineage(registry, DETECTOR_ID, TRACKER_ID),
        "environment": environment_snapshot(extra={"profile": args.profile}),
        "summary": summarize(measurements),
        "runs": measurements_as_dicts(measurements),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({"output": str(args.output), "summary": report["summary"]}, indent=2))
    return 0 if all(item.error is None for item in measurements) else 1


if __name__ == "__main__":
    raise SystemExit(main())
