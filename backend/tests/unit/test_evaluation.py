from __future__ import annotations

import json
import uuid
from pathlib import Path

import pytest
from PIL import Image, ImageDraw

from person_search.ai.selectors import RepresentativeFrameSelector, SelectorSettings
from person_search.evaluation.environment import environment_snapshot, gpu_snapshot
from person_search.evaluation.metrics import (
    Box,
    GalleryItem,
    QueryOutcome,
    detection_metrics,
    iou,
    match_boxes,
    rank_gallery,
    recall_summary,
    tracking_metrics,
    wilson_interval,
)
from person_search.evaluation.wildtrack_eval import (
    ANNOTATION_UNIT_MS,
    ImageSequenceSource,
    build_report,
    evaluate_camera,
    load_ground_truth,
    run_queries,
)
from person_search.services.searches import attributes_prompt
from person_search.storage.contracts import BoundingBoxPixels
from person_search.workers.contracts import (
    Detection,
    EmbeddingVector,
    ModelLineage,
    TrackState,
    TrackUpdate,
)
from person_search.workers.production import ProductionPipeline

pytestmark = pytest.mark.unit

SHA = "e" * 64
DETECTOR = ModelLineage("detector", "1", SHA)
TRACKER = ModelLineage("tracker", "1", SHA)
ENCODER = ModelLineage("encoder", "encoder_v1", SHA)


def box(x1, y1, x2, y2):
    return Box(x1, y1, x2, y2)


def test_iou_and_greedy_one_to_one_matching():
    a, b = box(0, 0, 10, 10), box(5, 0, 15, 10)
    assert iou(a, a) == 1.0
    assert iou(a, b) == pytest.approx(50 / 150)
    assert iou(a, box(20, 20, 30, 30)) == 0.0
    matches = match_boxes([a, box(0, 0, 10, 11)], [a], 0.5)
    assert [(p, t) for p, t, _ in matches] == [(0, 0)]
    assert Box.from_inclusive(0, 0, 9, 9) == box(0, 0, 10, 10)
    with pytest.raises(ValueError):
        box(5, 5, 5, 10)


def test_detection_metrics_count_duplicates_and_misses():
    truths = {0: [(1, box(0, 0, 10, 10)), (2, box(50, 50, 60, 60))], 5: [(1, box(0, 0, 10, 10))]}
    predictions = {
        0: [box(0, 0, 10, 10), box(0, 0, 10, 10.5), box(100, 100, 110, 110)],
        5: [],
    }

    metrics = detection_metrics(predictions, truths)

    assert (metrics.true_positives, metrics.false_positives) == (1, 2)
    assert (metrics.false_negatives, metrics.duplicates) == (2, 1)
    assert metrics.as_dict()["precision"] == pytest.approx(0.3333)
    assert metrics.as_dict()["recall"] == pytest.approx(0.3333)
    empty = detection_metrics({}, {})
    assert empty.precision is None and empty.recall is None


def test_tracking_metrics_fragmentation_switches_misses_and_labels():
    person = box(0, 0, 10, 20)
    other = box(100, 0, 110, 20)
    truths = {
        0: [(1, person), (2, other)],
        5: [(1, person), (2, other)],
        10: [(1, person), (3, box(200, 0, 210, 20))],
    }
    tracks = {
        0: [("t1", person), ("t9", other)],
        5: [("t1", person), ("t9", other), ("t8", box(0, 0, 10, 20.5))],
        10: [("t2", person), ("t9", box(100, 0, 110, 20))],
    }

    metrics = tracking_metrics(tracks, truths)

    assert metrics.ground_truth_people == 3
    assert metrics.matched_people == 2
    assert metrics.missed_people == [3]
    assert metrics.fragmented_people == 1 and metrics.track_breaks == 1
    assert metrics.identity_switches == 1
    assert metrics.duplicate_track_frames == 1
    assert metrics.track_labels == {"t1": 1, "t2": 1, "t9": 2, "t8": None}
    assert metrics.unmatched_tracks == 1
    assert tracking_metrics(tracks, truths, minimum_visible_frames=3).ground_truth_people == 1


def gallery_item(key, person, camera="C1", frame=0, vector=(1.0, 0.0), area=None):
    return GalleryItem(key, person, camera, frame, area or box(40, 40, 50, 50), vector)


def test_rank_gallery_excludes_exact_query_and_reports_first_positive():
    gallery = [
        gallery_item("exact", 7, vector=(1.0, 0.0), area=box(0, 0, 10, 10)),
        gallery_item("near-negative", 8, vector=(0.9, 0.1)),
        gallery_item("positive", 7, camera="C2", vector=(0.5, 0.5)),
        gallery_item("unlabeled", None, vector=(0.0, 1.0)),
    ]

    outcome = rank_gallery(
        "Q1", "image", 7, (1.0, 0.0), gallery, exclude=("C1", 0, box(0, 0, 10, 10))
    )

    assert [item[0] for item in outcome.top] == ["near-negative", "positive", "unlabeled"]
    assert outcome.first_positive_rank == 2 and outcome.positives == 1
    assert outcome.hit(4) and not outcome.hit(1)


def test_recall_summary_skips_queries_without_positive():
    gallery = [gallery_item("a", 1), gallery_item("b", 2, vector=(0.0, 1.0))]
    outcomes = [
        rank_gallery("Q1", "text", 1, (1.0, 0.0), gallery),
        rank_gallery("Q2", "text", 2, (1.0, 0.0), gallery),
        rank_gallery("Q3", "text", 99, (1.0, 0.0), gallery),
    ]

    summary = recall_summary(outcomes, ks=(1, 2))["text"]

    assert summary["queries"] == 3 and summary["evaluable_queries"] == 2
    assert summary["queries_without_positive"] == ["Q3"]
    assert summary["recall@1"] == 0.5 and summary["recall@2"] == 1.0
    assert summary["mean_reciprocal_rank"] == 0.75


COLORS = {11: (220, 30, 30), 22: (30, 30, 220)}
PEOPLE = {11: (100, 200, 260, 700), 22: (900, 150, 1060, 650)}
FRAMES = (0, 5, 10, 15)


def write_dataset(root: Path) -> None:
    (root / "annotations_positions").mkdir(parents=True)
    (root / "Image_subsets" / "C1").mkdir(parents=True)
    for frame in FRAMES:
        rows = []
        image = Image.new("RGB", (1920, 1080), (128, 128, 128))
        draw = ImageDraw.Draw(image)
        for person, (xmin, ymin, xmax, ymax) in PEOPLE.items():
            if person == 22 and frame == 15:
                continue
            draw.rectangle((xmin, ymin, xmax, ymax), fill=COLORS[person])
            for x in range(xmin, xmax, 6):
                draw.line((x, ymin, x, ymax), fill=(0, 0, 0))
            views = [
                {"viewNum": view, "xmin": -1, "ymin": -1, "xmax": -1, "ymax": -1}
                for view in range(7)
            ]
            views[0] = {"viewNum": 0, "xmin": xmin, "ymin": ymin, "xmax": xmax, "ymax": ymax}
            rows.append({"personID": person, "positionID": person, "views": views})
        rows.append(
            {
                "personID": 99,
                "positionID": 1,
                "views": [
                    {"viewNum": view, "xmin": -5, "ymin": 10, "xmax": 30, "ymax": 200}
                    for view in range(7)
                ],
            }
        )
        (root / "annotations_positions" / f"{frame:08d}.json").write_text(json.dumps(rows))
        image.save(root / "Image_subsets" / "C1" / f"{frame:08d}.png")
        image.close()


def dominant_vector(image: Image.Image) -> tuple[float, ...]:
    red, _, blue = image.convert("RGB").resize((1, 1)).getpixel((0, 0))
    return (1.0, 0.0, 0.0, 0.0) if red > blue else (0.0, 1.0, 0.0, 0.0)


class Detector:
    lineage = DETECTOR

    def __init__(self, truths):
        self.truths = truths
        self.closed = False

    def open(self):
        return None

    def close(self):
        self.closed = True

    def detect(self, frame):
        number = frame.source_timestamp_ms // ANNOTATION_UNIT_MS
        detections = []
        for person, area in self.truths.get(number, []):
            if person == 99:
                continue
            detections.append(
                Detection(
                    BoundingBoxPixels(
                        int(area.x1),
                        int(area.y1),
                        int(area.x2 - area.x1),
                        int(area.y2 - area.y1),
                        frame.width,
                        frame.height,
                    ),
                    0,
                    "person",
                    0.9,
                    DETECTOR,
                )
            )
        return tuple(detections)


class Tracker:
    lineage = TRACKER

    def __init__(self):
        self.last = {}
        self.closed = False

    def open(self):
        return None

    def close(self):
        self.closed = True

    def update(self, frame, detections):
        updates = []
        for detection in detections:
            local = "bt-left" if detection.bbox.x < 500 else "bt-right"
            update = TrackUpdate(
                local,
                frame.camera_id,
                detection.bbox,
                frame.source_frame_index,
                frame.source_timestamp_ms,
                TrackState.ACTIVE,
                TRACKER,
            )
            self.last[local] = update
            updates.append(update)
        return tuple(updates)

    def flush(self):
        return tuple(
            TrackUpdate(
                item.local_track_id,
                item.camera_id,
                item.bbox,
                item.source_frame_index,
                item.source_timestamp_ms,
                TrackState.ENDED,
                TRACKER,
            )
            for item in self.last.values()
        )


class Encoder:
    lineage = ENCODER

    def __init__(self):
        self.closed = False

    def open(self):
        return None

    def close(self):
        self.closed = True

    def encode(self, crop):
        return EmbeddingVector(dominant_vector(crop), 4, True, ENCODER)


class Gateway:
    def __init__(self):
        self.calls = []

    def image(self, content, *, version, dimension):
        import io

        self.calls.append(("image", version, dimension))
        with Image.open(io.BytesIO(content)) as image:
            return dominant_vector(image)

    def text(self, text, *, version, dimension):
        self.calls.append(("text", text))
        return (1.0, 0.0, 0.0, 0.0) if "red" in text else (0.0, 1.0, 0.0, 0.0)


def test_ground_truth_and_image_sequence_follow_wildtrack_layout(tmp_path):
    write_dataset(tmp_path)
    truths = load_ground_truth(tmp_path, "C1")
    assert sorted(truths) == list(FRAMES)
    assert {person for person, _ in truths[0]} == {11, 22, 99}
    clipped = next(area for person, area in truths[0] if person == 99)
    assert clipped.x1 == 0.0 and clipped.x2 == 31.0
    assert {person for person, _ in truths[15]} == {11, 99}

    source = ImageSequenceSource(tmp_path / "Image_subsets" / "C1", "C1", limit=3)
    frames = list(source)
    assert [frame.source_frame_index for frame in frames] == [0, 1, 2]
    assert [frame.source_timestamp_ms for frame in frames] == [0, 500, 1000]
    assert source.frame_numbers == [0, 5, 10]
    for frame in frames:
        frame.image.close()
    with pytest.raises(ValueError):
        ImageSequenceSource(tmp_path / "missing", "C1")


def test_camera_evaluation_and_queries_produce_reproducible_report(tmp_path):
    write_dataset(tmp_path)
    truths = load_ground_truth(tmp_path, "C1")
    components = {}

    def build(camera_id, recorder):
        detector, tracker, encoder = Detector(truths), Tracker(), Encoder()
        components.update(detector=detector, tracker=tracker, encoder=encoder)
        selector = RepresentativeFrameSelector(
            processing_job_id=uuid.uuid4(),
            ai_config_version_id=uuid.uuid4(),
            detector=DETECTOR,
            tracker=TRACKER,
            encoder=ENCODER,
            settings=SelectorSettings(
                minimum_bbox_width=8, minimum_bbox_height=8, minimum_sharpness_variance=0.01
            ),
        )
        return ProductionPipeline(
            recorder.detector(detector),
            recorder.tracker(tracker),
            selector,
            encoder,
            sampling_interval=1,
            job_timeout_seconds=60,
        )

    source = ImageSequenceSource(tmp_path / "Image_subsets" / "C1", "C1")
    run = evaluate_camera("C1", source, truths, build)

    assert run.source_frames == 4 and run.encoded_tracks == 2
    assert run.detection["true_positives"] == 7
    assert run.detection["false_positives"] == 0
    assert run.detection["false_negatives"] == 4
    assert run.tracking["matched_people"] == 2 and run.tracking["missed_people"] == 1
    assert run.tracking["track_breaks"] == 0
    assert sorted(item.person_id for item in run.gallery) == [11, 22]
    assert all(value.closed for value in components.values())
    assert "detector" in run.timings

    queries = [
        {
            "id": "WT-Q900",
            "person_id": 11,
            "image_query": {
                "camera": "C1",
                "frame": "00000005",
                "path": "Image_subsets/C1/00000005.png",
                "bbox": dict(zip(("xmin", "ymin", "xmax", "ymax"), PEOPLE[11], strict=True)),
            },
            "text_query": "A person in a red jacket.",
            "attribute_query": {"upper_color": "red"},
        },
        {
            "id": "WT-Q901",
            "person_id": 22,
            "image_query": {
                "camera": "C1",
                "frame": "00000000",
                "path": "Image_subsets/C1/00000000.png",
                "bbox": dict(zip(("xmin", "ymin", "xmax", "ymax"), PEOPLE[22], strict=True)),
            },
            "text_query": "A person in a blue coat.",
            "attribute_query": {"upper_color": "blue"},
        },
    ]
    gateway = Gateway()
    outcomes = run_queries(
        tmp_path, queries, gateway, run.gallery, version="encoder_v1", dimension=4
    )

    assert len(outcomes) == 6
    assert ("text", attributes_prompt({"upper_color": "red"})) in gateway.calls
    report = build_report([run], outcomes, lineage={"sampling_interval": 1})
    assert report["schema"] == "person-search-wildtrack-evaluation/v1"
    assert report["totals"]["gallery_size"] == 2
    assert report["totals"]["detection"]["recall"] == pytest.approx(7 / 11, abs=1e-4)
    assert set(report["retrieval"]) == {"image", "text", "attribute"}
    evaluable = {mode: row["evaluable_queries"] for mode, row in report["retrieval"].items()}
    assert all(value <= 2 for value in evaluable.values())
    json.dumps(report)


def test_environment_snapshot_is_offline_safe():
    outputs = {
        "git": "abc123",
        "nvidia-smi": "Tesla T4, 15360 MiB, 535.104, Default",
    }

    def runner(command):
        return outputs.get(command[0])

    snapshot = environment_snapshot(runner=runner, extra={"profile": "colab_t4"})

    assert snapshot["git_commit"] == "abc123"
    assert snapshot["gpus"] == [
        {
            "name": "Tesla T4",
            "memory_total": "15360 MiB",
            "driver": "535.104",
            "compute_mode": "Default",
        }
    ]
    assert snapshot["profile"] == "colab_t4"
    assert gpu_snapshot(lambda command: None) == []


def test_wilson_interval_matches_known_values_and_recall_summary_reports_it():
    assert wilson_interval(0, 0) is None
    low, high = wilson_interval(5, 6)
    assert (low, high) == (0.4365, 0.9699)
    low, high = wilson_interval(0, 6)
    assert low == 0.0 and 0.38 < high < 0.40
    outcomes = [
        QueryOutcome(f"q{index}", "image", 1, 1, 1 if index < 5 else None, ()) for index in range(6)
    ]
    summary = recall_summary(outcomes)["image"]
    assert summary["recall@4"] == 0.8333
    assert summary["recall@4_ci95"] == (0.4365, 0.9699)
