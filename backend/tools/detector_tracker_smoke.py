"""Run the production detector and tracker over sampled frames from one video."""

from __future__ import annotations

import argparse
import json
import uuid

import av

from person_search.ai.detectors import build_yolo_detector, load_detector_settings
from person_search.ai.registry import load_registry
from person_search.ai.selectors import RepresentativeFrameSelector, load_selector_settings
from person_search.ai.trackers import build_bytetrack
from person_search.workers.contracts import ModelLineage, SampledFrame, SourceFrame, TrackState


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--registry", required=True)
    parser.add_argument("--artifact-root", required=True)
    parser.add_argument("--detector-settings", required=True)
    parser.add_argument("--selector-settings")
    parser.add_argument("--video", required=True)
    parser.add_argument("--frames", type=int, default=8)
    parser.add_argument("--interval", type=int, default=10)
    parser.add_argument("--device", default="cpu")
    args = parser.parse_args()
    if args.frames < 1 or args.interval < 1:
        parser.error("--frames and --interval must be positive")

    available = {"yolo11n_coco", "bytetrack_v1"}
    registry = load_registry(
        args.registry,
        artifact_root=args.artifact_root,
        preflight_available=available,
    )
    detector = build_yolo_detector(
        registry.detector("yolo11n_coco"),
        artifact_root=args.artifact_root,
        device=args.device,
        settings=load_detector_settings(args.detector_settings),
    )
    tracker = build_bytetrack(
        registry.tracker("bytetrack_v1"),
        artifact_root=args.artifact_root,
        device=args.device,
    )
    selector = None
    if args.selector_settings:
        encoder_entry = registry.encoder
        assert encoder_entry is not None
        selector = RepresentativeFrameSelector(
            processing_job_id=uuid.uuid4(),
            ai_config_version_id=uuid.uuid4(),
            detector=detector.lineage,
            tracker=tracker.lineage,
            encoder=ModelLineage(
                encoder_entry.id,
                encoder_entry.version,
                encoder_entry.artifact.sha256,
            ),
            settings=load_selector_settings(args.selector_settings),
        )
    camera_id = uuid.uuid4()
    active_ids: set[str] = set()
    detections_seen = 0
    sampled = 0
    detector.open()
    tracker.open()
    if selector:
        selector.open()
    container = av.open(args.video)
    last_frame = None
    try:
        for source_index, decoded in enumerate(container.decode(video=0)):
            if source_index % args.interval:
                continue
            image = decoded.to_image().convert("RGB")
            timestamp_ms = int(float(decoded.time or 0) * 1000)
            source = SourceFrame(
                camera_id,
                source_index,
                timestamp_ms,
                image,
                image.width,
                image.height,
            )
            frame = SampledFrame(source, args.interval, sampled)
            last_frame = frame
            detections = detector.detect(frame)
            detections_seen += len(detections)
            updates = tracker.update(frame, detections)
            active_ids.update(
                update.local_track_id
                for update in updates
                if update.state is TrackState.ACTIVE
            )
            if selector:
                for update in updates:
                    selector.consider(frame, update)
            sampled += 1
            if sampled == args.frames:
                break
        ended = tracker.flush()
        if selector and last_frame:
            for update in ended:
                selector.consider(last_frame, update)
            selected = selector.flush()
        else:
            selected = ()
    finally:
        container.close()
        if selector:
            selector.close()
        tracker.close()
        detector.close()
    payload = {
        "status": "ok",
        "sampled_frames": sampled,
        "detections_seen": detections_seen,
        "active_track_ids": sorted(active_ids),
        "ended_track_ids": sorted(item.local_track_id for item in ended),
        "representative_tracks": len(selected),
        "low_quality_tracks": sum(
            item.quality_flag.value == "LOW_QUALITY" for item in selected
        ),
    }
    print(json.dumps(payload, sort_keys=True))
    images = {
        id(item.representative.frame.image): item.representative.frame.image
        for item in selected
    }
    for image in images.values():
        image.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
