"""Run one real video frame through the registry-backed YOLO detector."""

from __future__ import annotations

import argparse
import json
import uuid
from pathlib import Path

import av

from person_search.ai.detectors import build_yolo_detector, load_detector_settings
from person_search.ai.registry import load_registry
from person_search.workers.contracts import SampledFrame, SourceFrame


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--registry", required=True)
    parser.add_argument("--artifact-root", required=True)
    parser.add_argument("--settings", required=True)
    parser.add_argument("--video", required=True)
    parser.add_argument("--detector-id", default="yolo11n_coco")
    parser.add_argument("--device", default="cpu")
    args = parser.parse_args()

    registry = load_registry(
        args.registry,
        artifact_root=args.artifact_root,
        preflight_available={args.detector_id},
    )
    entry = registry.detector(args.detector_id)
    detector = build_yolo_detector(
        entry,
        artifact_root=args.artifact_root,
        device=args.device,
        settings=load_detector_settings(args.settings),
    )
    container = av.open(str(Path(args.video).resolve()))
    try:
        decoded = next(container.decode(video=0)).to_image().convert("RGB")
    finally:
        container.close()
    source = SourceFrame(uuid.uuid4(), 0, 0, decoded, decoded.width, decoded.height)
    frame = SampledFrame(source, sampling_interval=1, sample_sequence=0)

    detector.open()
    try:
        detections = detector.detect(frame)
        metrics = detector.metrics
    finally:
        detector.close()
    print(
        json.dumps(
            {
                "status": "ok",
                "detector_id": entry.id,
                "device": args.device,
                "frame_size": [decoded.width, decoded.height],
                "person_detections": len(detections),
                "latency_ms": metrics.last_latency_ms,
                "boxes": [
                    {
                        "x": item.bbox.x,
                        "y": item.bbox.y,
                        "width": item.bbox.width,
                        "height": item.bbox.height,
                    }
                    for item in detections
                ],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
