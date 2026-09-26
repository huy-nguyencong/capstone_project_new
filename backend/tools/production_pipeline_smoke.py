"""Run the AIW-16 production pipeline over a bounded real-video fixture."""

from __future__ import annotations

import argparse
import itertools
import json
import uuid
from pathlib import Path
from types import SimpleNamespace

from person_search.ai.registry import load_registry
from person_search.workers.production import build_production_pipeline
from person_search.workers.sources import FileFrameSource


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--registry", required=True)
    parser.add_argument("--artifact-root", required=True)
    parser.add_argument("--detector-settings", required=True)
    parser.add_argument("--selector-settings", required=True)
    parser.add_argument("--rasa-settings", required=True)
    parser.add_argument("--video", required=True)
    parser.add_argument("--source-frames", type=int, default=80)
    parser.add_argument("--interval", type=int, default=10)
    parser.add_argument("--device", default="cpu")
    args = parser.parse_args()
    if args.source_frames < 1 or args.interval < 1:
        parser.error("--source-frames and --interval must be positive")

    registry = load_registry(
        args.registry,
        artifact_root=args.artifact_root,
        preflight_available={"yolo11n_coco", "bytetrack_v1", "rasa_cuhk_pedes_v1"},
    )
    assert registry.encoder is not None
    detector = registry.detector("yolo11n_coco")
    tracker = registry.tracker("bytetrack_v1")
    config_id = uuid.uuid4()
    config = SimpleNamespace(
        detector_name=detector.id,
        detector_version=detector.version,
        tracker_name=tracker.id,
        tracker_version=tracker.version,
        encoder_name=registry.encoder.id,
        encoder_version=registry.encoder.version,
        encoder_dimension=registry.encoder.dimension,
        checkpoint_sha256=registry.encoder.artifact.sha256,
    )
    pipeline = build_production_pipeline(
        registry,
        config,
        artifact_root=args.artifact_root,
        detector_settings_path=args.detector_settings,
        selector_settings_path=args.selector_settings,
        rasa_settings_path=args.rasa_settings,
        processing_job_id=uuid.uuid4(),
        ai_config_version_id=config_id,
        sampling_interval=args.interval,
        job_timeout_seconds=600,
        device=args.device,
    )
    camera_id = uuid.uuid4()
    fixture_size = Path(args.video).stat().st_size
    source = FileFrameSource(max_bytes=fixture_size).open(args.video, camera_id=camera_id)
    with source:
        result = pipeline.run(itertools.islice(source, args.source_frames))
    payload = {
        "status": "ok",
        "source_frames": result.source_frames,
        "sampled_frames": result.sampled_frames,
        "detections": result.detections,
        "track_updates": result.track_updates,
        "encoded_tracks": len(result.encoded_tracks),
        "embedding_dimensions": sorted(
            {item.embedding.dimension for item in result.encoded_tracks}
        ),
        "encoder_versions": sorted(
            {item.embedding.encoder.version for item in result.encoded_tracks}
        ),
        "timings_ms": {
            item.stage: round(item.elapsed_ms, 3) for item in result.timings
        },
    }
    images = {
        id(item.track.representative.frame.image): item.track.representative.frame.image
        for item in result.encoded_tracks
    }
    for image in images.values():
        image.close()
    if not result.encoded_tracks:
        raise RuntimeError("Production fixture did not produce a completed encoded track.")
    print(json.dumps(payload, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
