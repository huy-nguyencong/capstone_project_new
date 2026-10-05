from __future__ import annotations

import argparse
import json
import os
import uuid
from pathlib import Path
from types import SimpleNamespace

from person_search.ai.config_loader import ProductionComponentFactory
from person_search.ai.registry import load_registry
from person_search.ai.selectors import RepresentativeFrameSelector, load_selector_settings
from person_search.evaluation.environment import (
    environment_snapshot,
    registry_lineage,
    settings_lineage,
)
from person_search.evaluation.metrics import Box, GalleryItem
from person_search.evaluation.wildtrack_eval import (
    CAMERAS,
    QUERY_MODES,
    CameraRun,
    ImageSequenceSource,
    build_report,
    evaluate_camera,
    load_ground_truth,
    run_queries,
)
from person_search.workers.contracts import ModelLineage
from person_search.workers.production import ProductionPipeline

DETECTOR_ID = "yolo11n_coco"
TRACKER_ID = "bytetrack_v1"
GALLERY_CACHE_SCHEMA = "person-search-wildtrack-gallery-cache/v1"


def _dump_runs(runs, *, path: Path, key: dict) -> None:
    """Keep the pipeline output (metrics, timings, gallery with embeddings) for later query runs."""

    payload = {
        "schema": GALLERY_CACHE_SCHEMA,
        "key": key,
        "runs": [
            {
                "camera": run.camera,
                "detection": run.detection,
                "tracking": run.tracking,
                "source_frames": run.source_frames,
                "sampled_frames": run.sampled_frames,
                "encoded_tracks": run.encoded_tracks,
                "timings": run.timings,
                "gallery": [
                    {
                        "key": item.key,
                        "person_id": item.person_id,
                        "camera": item.camera,
                        "frame": item.frame,
                        "box": [item.box.x1, item.box.y1, item.box.x2, item.box.y2],
                        "embedding": list(item.embedding),
                    }
                    for item in run.gallery
                ],
            }
            for run in runs
        ],
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _load_runs(path: Path, *, key: dict) -> list:
    """Cached camera runs whose key matches; a cache may hold only some of the cameras."""

    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("schema") != GALLERY_CACHE_SCHEMA:
        raise SystemExit(f"Unsupported gallery cache: {path}")
    if payload.get("key") != key:
        raise SystemExit(
            "Gallery cache was built with other models, settings or cameras; "
            f"delete it or run without --gallery-cache: {path}"
        )
    runs = []
    for row in payload["runs"]:
        runs.append(
            CameraRun(
                camera=row["camera"],
                detection=row["detection"],
                tracking=row["tracking"],
                gallery=[
                    GalleryItem(
                        key=item["key"],
                        person_id=item["person_id"],
                        camera=item["camera"],
                        frame=item["frame"],
                        box=Box(*item["box"]),
                        embedding=tuple(item["embedding"]),
                    )
                    for item in row["gallery"]
                ],
                source_frames=row["source_frames"],
                sampled_frames=row["sampled_frames"],
                encoded_tracks=row["encoded_tracks"],
                timings=row["timings"],
            )
        )
    return runs


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Evaluate detection, tracking and three retrieval modes on WILDTRACK."
    )
    parser.add_argument("--dataset-root", type=Path, required=True)
    parser.add_argument("--queries", type=Path, required=True)
    parser.add_argument("--registry", type=Path, required=True)
    parser.add_argument("--artifact-root", type=Path, required=True)
    parser.add_argument("--config-root", type=Path, default=Path("config"))
    parser.add_argument("--cameras", default=",".join(CAMERAS))
    parser.add_argument("--sampling-interval", type=int, default=1)
    parser.add_argument("--frame-limit", type=int)
    parser.add_argument("--modes", default=",".join(QUERY_MODES))
    parser.add_argument("--iou-threshold", type=float, default=0.5)
    parser.add_argument("--job-timeout-seconds", type=float, default=7200.0)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--gallery-cache",
        type=Path,
        help="JSON file with the pipeline output; reused when it exists and matches the models, "
        "settings and cameras, otherwise written after the pipeline has run",
    )
    args = parser.parse_args()
    if args.sampling_interval < 1:
        parser.error("--sampling-interval must be positive")
    cameras = [item.strip() for item in args.cameras.split(",") if item.strip()]
    if not cameras or set(cameras) - set(CAMERAS):
        parser.error("--cameras must list C1..C7")
    modes = [item.strip() for item in args.modes.split(",") if item.strip()]
    if not modes or set(modes) - set(QUERY_MODES):
        parser.error("--modes must be image,text,attribute")

    registry = load_registry(
        args.registry,
        artifact_root=args.artifact_root,
        preflight_available={DETECTOR_ID, TRACKER_ID, "rasa_cuhk_pedes_v1"},
    )
    selection = registry.resolve(DETECTOR_ID, TRACKER_ID)
    components = ProductionComponentFactory.from_environment(
        artifact_root=args.artifact_root, config_root=args.config_root
    )
    selector_path = Path(
        os.getenv("PERSON_SEARCH_SELECTOR_CONFIG")
        or args.config_root / "representative_selector.json"
    )
    selector_settings = load_selector_settings(selector_path)
    encoder_lineage = ModelLineage(
        selection.encoder.id, selection.encoder.version, selection.encoder.artifact.sha256
    )
    evaluation_id = uuid.uuid4()

    def build_pipeline(camera_id, recorder):
        detector = components.detector(selection)
        tracker = components.tracker(selection)
        selector = RepresentativeFrameSelector(
            processing_job_id=evaluation_id,
            ai_config_version_id=evaluation_id,
            detector=detector.lineage,
            tracker=tracker.lineage,
            encoder=encoder_lineage,
            settings=selector_settings,
        )
        return ProductionPipeline(
            recorder.detector(detector),
            recorder.tracker(tracker),
            selector,
            components.image_encoder(selection),
            sampling_interval=args.sampling_interval,
            job_timeout_seconds=args.job_timeout_seconds,
        )

    settings_paths = {
        "detector": Path(
            os.getenv("PERSON_SEARCH_DETECTOR_CONFIG")
            or args.config_root / "ultralytics_yolo_detector.json"
        ),
        "selector": selector_path,
        "rasa": Path(
            os.getenv("PERSON_SEARCH_RASA_CONFIG")
            or args.config_root / "rasa_cuhk_pedes_runtime.json"
        ),
        "tracker": args.artifact_root / selection.tracker.artifact.relative_path,
    }
    cache_key = {
        "models": registry_lineage(registry, DETECTOR_ID, TRACKER_ID),
        "settings": settings_lineage(settings_paths),
        "cameras": cameras,
        "sampling_interval": args.sampling_interval,
        "frame_limit": args.frame_limit,
        "iou_threshold": args.iou_threshold,
    }
    # The camera list is not part of the key: a cache may be filled one camera at a time.
    cache_key = json.loads(json.dumps({**cache_key, "cameras": None}, default=str))
    cached = {}
    if args.gallery_cache is not None and args.gallery_cache.is_file():
        cached = {run.camera: run for run in _load_runs(args.gallery_cache, key=cache_key)}
        print(
            json.dumps(
                {
                    "gallery_cache": str(args.gallery_cache),
                    "cached_cameras": sorted(cached),
                    "tracks": sum(run.encoded_tracks for run in cached.values()),
                }
            ),
            flush=True,
        )
    runs = []
    for camera in cameras:
        if camera in cached:
            runs.append(cached[camera])
            continue
        source = ImageSequenceSource(
            args.dataset_root / "Image_subsets" / camera, camera, limit=args.frame_limit
        )
        truths = load_ground_truth(args.dataset_root, camera)
        run = evaluate_camera(
            camera, source, truths, build_pipeline, iou_threshold=args.iou_threshold
        )
        runs.append(run)
        cached[camera] = run
        print(
            json.dumps(
                {"camera": camera, "tracks": run.encoded_tracks, "detection": run.detection}
            ),
            flush=True,
        )
        if args.gallery_cache is not None:
            # Written after every camera so that an interrupted run resumes where it stopped.
            _dump_runs(
                [cached[name] for name in sorted(cached)], path=args.gallery_cache, key=cache_key
            )

    query_set = json.loads(args.queries.read_text(encoding="utf-8"))
    gateway = components.query_gateway(SimpleNamespace(encoder=selection.encoder))
    gateway.open()
    try:
        outcomes = run_queries(
            args.dataset_root,
            query_set["queries"],
            gateway,
            [item for run in runs for item in run.gallery],
            version=selection.encoder.version,
            dimension=selection.encoder.dimension,
            modes=modes,
        )
    finally:
        gateway.close()

    report = build_report(
        runs,
        outcomes,
        lineage={
            "models": registry_lineage(registry, DETECTOR_ID, TRACKER_ID),
            "settings": settings_lineage(settings_paths),
            "gallery_cache": str(args.gallery_cache) if args.gallery_cache else None,
            "query_set": {
                "schema": query_set.get("schema"),
                "label_status": query_set.get("label_status"),
                "dataset_tree_sha256": query_set.get("dataset_tree_sha256"),
                "count": len(query_set["queries"]),
            },
            "sampling_interval": args.sampling_interval,
            "frame_limit": args.frame_limit,
            "iou_threshold": args.iou_threshold,
            "cameras": cameras,
            "modes": modes,
            "rerank": False,
            "source": "WILDTRACK Image_subsets with annotations_positions",
            "environment": environment_snapshot(),
        },
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({"output": str(args.output), "retrieval": report["retrieval"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
