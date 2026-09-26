from __future__ import annotations

import io
import json
import uuid
from collections import defaultdict
from collections.abc import Callable, Iterator, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from PIL import Image

from person_search.evaluation.metrics import (
    Box,
    GalleryItem,
    QueryOutcome,
    detection_metrics,
    rank_gallery,
    recall_summary,
    tracking_metrics,
)
from person_search.services.searches import attributes_prompt
from person_search.workers.contracts import SourceFrame, TrackState

FRAME_WIDTH, FRAME_HEIGHT = 1920, 1080
ANNOTATION_UNIT_MS = 100
CAMERAS = tuple(f"C{index}" for index in range(1, 8))
REPORT_SCHEMA = "person-search-wildtrack-evaluation/v1"
QUERY_MODES = ("image", "text", "attribute")


def camera_uuid(camera: str) -> uuid.UUID:
    return uuid.uuid5(uuid.NAMESPACE_URL, f"wildtrack:{camera}")


def _clip(value: int, upper: int) -> int:
    return max(0, min(upper - 1, value))


def load_ground_truth(dataset_root: Path, camera: str) -> dict[int, list[tuple[int, Box]]]:
    view_number = int(camera[1:]) - 1
    truths: dict[int, list[tuple[int, Box]]] = {}
    for path in sorted((dataset_root / "annotations_positions").glob("*.json")):
        frame = int(path.stem)
        rows = json.loads(path.read_text(encoding="utf-8"))
        items = []
        for row in rows:
            view = next(
                (item for item in row.get("views", []) if item.get("viewNum") == view_number),
                None,
            )
            if view is None:
                continue
            xmin, ymin, xmax, ymax = (view.get(key) for key in ("xmin", "ymin", "xmax", "ymax"))
            if (xmin, ymin, xmax, ymax) == (-1, -1, -1, -1):
                continue
            if any(type(value) is not int for value in (xmin, ymin, xmax, ymax)):
                continue
            left, top = _clip(xmin, FRAME_WIDTH), _clip(ymin, FRAME_HEIGHT)
            right, bottom = _clip(xmax, FRAME_WIDTH), _clip(ymax, FRAME_HEIGHT)
            if right <= left or bottom <= top:
                continue
            items.append((int(row["personID"]), Box.from_inclusive(left, top, right, bottom)))
        truths[frame] = items
    return truths


class ImageSequenceSource:
    def __init__(self, directory: Path, camera: str, *, limit: int | None = None) -> None:
        paths = sorted(directory.glob("*.png"))
        if limit is not None:
            paths = paths[:limit]
        if not paths:
            raise ValueError("Image sequence is empty.")
        self.paths = paths
        self.camera = camera
        self.camera_id = camera_uuid(camera)
        self.frame_numbers = [int(path.stem) for path in paths]
        self.closed = False

    def __enter__(self) -> ImageSequenceSource:
        return self

    def __exit__(self, *args: object) -> None:
        self.closed = True

    def __iter__(self) -> Iterator[SourceFrame]:
        for index, path in enumerate(self.paths):
            with Image.open(path) as opened:
                image = opened.convert("RGB")
            yield SourceFrame(
                self.camera_id,
                index,
                self.frame_numbers[index] * ANNOTATION_UNIT_MS,
                image,
                image.width,
                image.height,
            )


class _RecordingDetector:
    def __init__(self, inner: Any, sink: dict[int, list[Box]]) -> None:
        self.inner = inner
        self.sink = sink
        self.lineage = inner.lineage

    def open(self) -> None:
        self.inner.open()

    def close(self) -> None:
        self.inner.close()

    def detect(self, frame: Any) -> Sequence[Any]:
        detections = tuple(self.inner.detect(frame))
        self.sink[frame.source_frame_index] = [
            Box.from_xywh(item.bbox.x, item.bbox.y, item.bbox.width, item.bbox.height)
            for item in detections
        ]
        return detections


class _RecordingTracker:
    def __init__(self, inner: Any, sink: dict[int, list[tuple[str, Box]]]) -> None:
        self.inner = inner
        self.sink = sink
        self.lineage = inner.lineage

    def open(self) -> None:
        self.inner.open()

    def close(self) -> None:
        self.inner.close()

    def update(self, frame: Any, detections: Sequence[Any]) -> Sequence[Any]:
        updates = tuple(self.inner.update(frame, detections))
        rows = self.sink.setdefault(frame.source_frame_index, [])
        for update in updates:
            current = update.source_frame_index == frame.source_frame_index
            if update.state is TrackState.ACTIVE and current:
                box = update.bbox
                rows.append(
                    (update.local_track_id, Box.from_xywh(box.x, box.y, box.width, box.height))
                )
        return updates

    def flush(self) -> Sequence[Any]:
        return tuple(self.inner.flush())


@dataclass
class Recorder:
    detections: dict[int, list[Box]] = field(default_factory=dict)
    tracks: dict[int, list[tuple[str, Box]]] = field(default_factory=dict)

    def detector(self, inner: Any) -> _RecordingDetector:
        return _RecordingDetector(inner, self.detections)

    def tracker(self, inner: Any) -> _RecordingTracker:
        return _RecordingTracker(inner, self.tracks)


@dataclass
class CameraRun:
    camera: str
    detection: dict[str, Any]
    tracking: dict[str, Any]
    gallery: list[GalleryItem]
    source_frames: int
    sampled_frames: int
    encoded_tracks: int
    timings: dict[str, dict[str, float]]


PipelineBuilder = Callable[[uuid.UUID, Recorder], Any]


def evaluate_camera(
    camera: str,
    source: ImageSequenceSource,
    truths: Mapping[int, Sequence[tuple[int, Box]]],
    build_pipeline: PipelineBuilder,
    *,
    iou_threshold: float = 0.5,
) -> CameraRun:
    recorder = Recorder()
    pipeline = build_pipeline(source.camera_id, recorder)
    with source:
        result = pipeline.run(source)
    numbers = source.frame_numbers
    detections = {numbers[index]: boxes for index, boxes in recorder.detections.items()}
    tracks = {numbers[index]: rows for index, rows in recorder.tracks.items()}
    evaluated = {frame: truths.get(frame, []) for frame in detections}
    detection = detection_metrics(detections, evaluated, threshold=iou_threshold)
    tracking = tracking_metrics(tracks, evaluated, threshold=iou_threshold)
    gallery = []
    images = {}
    try:
        for encoded in result.encoded_tracks:
            track = encoded.track
            representative = track.representative
            images[id(representative.frame.image)] = representative.frame.image
            bbox = representative.bbox
            gallery.append(
                GalleryItem(
                    key=f"{camera}:{track.local_track_id}",
                    person_id=tracking.track_labels.get(track.local_track_id),
                    camera=camera,
                    frame=numbers[representative.frame.source_frame_index],
                    box=Box.from_xywh(bbox.x, bbox.y, bbox.width, bbox.height),
                    embedding=tuple(encoded.embedding.values),
                )
            )
    finally:
        for image in images.values():
            image.close()
    return CameraRun(
        camera=camera,
        detection=detection.as_dict(),
        tracking=tracking.as_dict(),
        gallery=gallery,
        source_frames=result.source_frames,
        sampled_frames=result.sampled_frames,
        encoded_tracks=len(result.encoded_tracks),
        timings={
            timing.stage: {
                "calls": timing.calls,
                "total_ms": round(timing.elapsed_ms, 3),
                "mean_ms": round(timing.elapsed_ms / timing.calls, 3) if timing.calls else 0.0,
            }
            for timing in result.timings
        },
    )


def query_crop_png(dataset_root: Path, image_query: Mapping[str, Any]) -> bytes:
    bbox = image_query["bbox"]
    path = dataset_root.joinpath(*str(image_query["path"]).split("/"))
    with Image.open(path) as opened:
        crop = opened.convert("RGB").crop(
            (bbox["xmin"], bbox["ymin"], bbox["xmax"] + 1, bbox["ymax"] + 1)
        )
    output = io.BytesIO()
    try:
        crop.save(output, format="PNG")
        return output.getvalue()
    finally:
        crop.close()


def run_queries(
    dataset_root: Path,
    queries: Sequence[Mapping[str, Any]],
    gateway: Any,
    gallery: Sequence[GalleryItem],
    *,
    version: str,
    dimension: int,
    modes: Sequence[str] = QUERY_MODES,
) -> list[QueryOutcome]:
    outcomes = []
    for query in queries:
        image_query = query["image_query"]
        bbox = image_query["bbox"]
        exclude = (
            image_query["camera"],
            int(image_query["frame"]),
            Box.from_inclusive(bbox["xmin"], bbox["ymin"], bbox["xmax"], bbox["ymax"]),
        )
        for mode in modes:
            if mode == "image":
                embedding = gateway.image(
                    query_crop_png(dataset_root, image_query), version=version, dimension=dimension
                )
            elif mode == "text":
                embedding = gateway.text(query["text_query"], version=version, dimension=dimension)
            elif mode == "attribute":
                embedding = gateway.text(
                    attributes_prompt(query["attribute_query"]),
                    version=version,
                    dimension=dimension,
                )
            else:
                raise ValueError(f"Unsupported query mode: {mode}")
            outcomes.append(
                rank_gallery(
                    query["id"],
                    mode,
                    int(query["person_id"]),
                    embedding,
                    gallery,
                    exclude=exclude,
                )
            )
    return outcomes


def _sum_dicts(rows: Sequence[Mapping[str, Any]], keys: Sequence[str]) -> dict[str, int]:
    return {key: sum(int(row[key]) for row in rows) for key in keys}


def build_report(
    runs: Sequence[CameraRun],
    outcomes: Sequence[QueryOutcome],
    *,
    lineage: Mapping[str, Any],
    examples_per_mode: int = 3,
) -> dict[str, Any]:
    detection_totals = _sum_dicts(
        [run.detection for run in runs],
        ("true_positives", "false_positives", "false_negatives", "duplicates"),
    )
    tp = detection_totals["true_positives"]
    precision_base = tp + detection_totals["false_positives"]
    recall_base = tp + detection_totals["false_negatives"]
    detection_totals["precision"] = round(tp / precision_base, 4) if precision_base else None
    detection_totals["recall"] = round(tp / recall_base, 4) if recall_base else None
    tracking_totals = _sum_dicts(
        [run.tracking for run in runs],
        (
            "ground_truth_people",
            "matched_people",
            "missed_people",
            "predicted_tracks",
            "unmatched_tracks",
            "fragmented_people",
            "track_breaks",
            "identity_switches",
            "impure_tracks",
            "duplicate_track_frames",
        ),
    )
    examples: dict[str, dict[str, list[dict[str, Any]]]] = defaultdict(
        lambda: {"success": [], "failure": []}
    )
    for outcome in outcomes:
        if outcome.positives == 0:
            continue
        bucket = "success" if outcome.hit(4) else "failure"
        if len(examples[outcome.mode][bucket]) < examples_per_mode:
            examples[outcome.mode][bucket].append(outcome.as_dict())
    return {
        "schema": REPORT_SCHEMA,
        "lineage": dict(lineage),
        "cameras": {
            run.camera: {
                "source_frames": run.source_frames,
                "sampled_frames": run.sampled_frames,
                "encoded_tracks": run.encoded_tracks,
                "gallery_labeled": sum(1 for item in run.gallery if item.person_id is not None),
                "detection": run.detection,
                "tracking": run.tracking,
                "timings": run.timings,
            }
            for run in runs
        },
        "totals": {
            "detection": detection_totals,
            "tracking": tracking_totals,
            "gallery_size": sum(len(run.gallery) for run in runs),
        },
        "retrieval": recall_summary(outcomes),
        "examples": dict(examples),
        "queries": [outcome.as_dict() for outcome in outcomes],
    }
