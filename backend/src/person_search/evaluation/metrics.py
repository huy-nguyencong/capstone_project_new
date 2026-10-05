from __future__ import annotations

import math
from collections import Counter, defaultdict
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

RECALL_KS = (4, 8, 12, 16)


@dataclass(frozen=True, slots=True)
class Box:
    x1: float
    y1: float
    x2: float
    y2: float

    def __post_init__(self) -> None:
        if not all(math.isfinite(value) for value in (self.x1, self.y1, self.x2, self.y2)):
            raise ValueError("Box coordinates must be finite.")
        if self.x2 <= self.x1 or self.y2 <= self.y1:
            raise ValueError("Box must have positive area.")

    @classmethod
    def from_inclusive(cls, xmin: int, ymin: int, xmax: int, ymax: int) -> Box:
        return cls(float(xmin), float(ymin), float(xmax + 1), float(ymax + 1))

    @classmethod
    def from_xywh(cls, x: float, y: float, width: float, height: float) -> Box:
        return cls(float(x), float(y), float(x + width), float(y + height))

    @property
    def area(self) -> float:
        return (self.x2 - self.x1) * (self.y2 - self.y1)


def iou(left: Box, right: Box) -> float:
    width = min(left.x2, right.x2) - max(left.x1, right.x1)
    height = min(left.y2, right.y2) - max(left.y1, right.y1)
    if width <= 0 or height <= 0:
        return 0.0
    intersection = width * height
    return intersection / (left.area + right.area - intersection)


def match_boxes(
    predictions: Sequence[Box], truths: Sequence[Box], threshold: float = 0.5
) -> list[tuple[int, int, float]]:
    candidates = sorted(
        (
            (iou(prediction, truth), prediction_index, truth_index)
            for prediction_index, prediction in enumerate(predictions)
            for truth_index, truth in enumerate(truths)
        ),
        key=lambda item: (-item[0], item[1], item[2]),
    )
    used_predictions: set[int] = set()
    used_truths: set[int] = set()
    matches = []
    for overlap, prediction_index, truth_index in candidates:
        if overlap < threshold:
            break
        if prediction_index in used_predictions or truth_index in used_truths:
            continue
        used_predictions.add(prediction_index)
        used_truths.add(truth_index)
        matches.append((prediction_index, truth_index, overlap))
    return matches


@dataclass(frozen=True, slots=True)
class DetectionMetrics:
    true_positives: int
    false_positives: int
    false_negatives: int
    duplicates: int

    @property
    def precision(self) -> float | None:
        total = self.true_positives + self.false_positives
        return self.true_positives / total if total else None

    @property
    def recall(self) -> float | None:
        total = self.true_positives + self.false_negatives
        return self.true_positives / total if total else None

    def as_dict(self) -> dict[str, Any]:
        return {
            "true_positives": self.true_positives,
            "false_positives": self.false_positives,
            "false_negatives": self.false_negatives,
            "duplicates": self.duplicates,
            "precision": _round(self.precision),
            "recall": _round(self.recall),
        }


def detection_metrics(
    predictions: Mapping[int, Sequence[Box]],
    truths: Mapping[int, Sequence[tuple[int, Box]]],
    *,
    threshold: float = 0.5,
) -> DetectionMetrics:
    tp = fp = fn = duplicates = 0
    for frame in sorted(set(predictions) | set(truths)):
        boxes = list(predictions.get(frame, ()))
        gt = [box for _, box in truths.get(frame, ())]
        matches = match_boxes(boxes, gt, threshold)
        matched_predictions = {item[0] for item in matches}
        tp += len(matches)
        fn += len(gt) - len(matches)
        for index, box in enumerate(boxes):
            if index in matched_predictions:
                continue
            fp += 1
            if any(iou(box, gt[truth]) >= threshold for _, truth, _ in matches):
                duplicates += 1
    return DetectionMetrics(tp, fp, fn, duplicates)


@dataclass(slots=True)
class TrackingMetrics:
    ground_truth_people: int
    matched_people: int
    missed_people: list[int]
    predicted_tracks: int
    unmatched_tracks: int
    fragmented_people: int
    track_breaks: int
    identity_switches: int
    impure_tracks: int
    duplicate_track_frames: int
    track_labels: dict[str, int | None] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "ground_truth_people": self.ground_truth_people,
            "matched_people": self.matched_people,
            "missed_people": len(self.missed_people),
            "missed_person_ids": sorted(self.missed_people),
            "predicted_tracks": self.predicted_tracks,
            "unmatched_tracks": self.unmatched_tracks,
            "fragmented_people": self.fragmented_people,
            "track_breaks": self.track_breaks,
            "identity_switches": self.identity_switches,
            "impure_tracks": self.impure_tracks,
            "duplicate_track_frames": self.duplicate_track_frames,
        }


def tracking_metrics(
    tracks: Mapping[int, Sequence[tuple[str, Box]]],
    truths: Mapping[int, Sequence[tuple[int, Box]]],
    *,
    threshold: float = 0.5,
    minimum_visible_frames: int = 1,
) -> TrackingMetrics:
    person_frames: Counter[int] = Counter()
    for rows in truths.values():
        for person_id, _ in rows:
            person_frames[person_id] += 1
    eligible = {
        person for person, count in person_frames.items() if count >= minimum_visible_frames
    }
    person_tracks: dict[int, set[str]] = defaultdict(set)
    track_people: dict[str, Counter[int]] = defaultdict(Counter)
    last_track: dict[int, str] = {}
    switches = 0
    duplicate_frames = 0
    all_tracks: set[str] = set()
    for frame in sorted(set(tracks) | set(truths)):
        predicted = list(tracks.get(frame, ()))
        gt = list(truths.get(frame, ()))
        all_tracks.update(track_id for track_id, _ in predicted)
        matches = match_boxes([box for _, box in predicted], [box for _, box in gt], threshold)
        matched_predictions = {item[0] for item in matches}
        for prediction_index, truth_index, _ in matches:
            track_id = predicted[prediction_index][0]
            person_id = gt[truth_index][0]
            person_tracks[person_id].add(track_id)
            track_people[track_id][person_id] += 1
            previous = last_track.get(person_id)
            if previous is not None and previous != track_id:
                switches += 1
            last_track[person_id] = track_id
        for index, (_, box) in enumerate(predicted):
            if index in matched_predictions:
                continue
            if any(iou(box, gt[truth][1]) >= threshold for _, truth, _ in matches):
                duplicate_frames += 1
    matched = {person for person in eligible if person_tracks.get(person)}
    fragmented = [person for person in matched if len(person_tracks[person]) > 1]
    labels: dict[str, int | None] = {}
    for track_id in all_tracks:
        counter = track_people.get(track_id)
        labels[track_id] = counter.most_common(1)[0][0] if counter else None
    return TrackingMetrics(
        ground_truth_people=len(eligible),
        matched_people=len(matched),
        missed_people=sorted(eligible - matched),
        predicted_tracks=len(all_tracks),
        unmatched_tracks=sum(1 for track in all_tracks if not track_people.get(track)),
        fragmented_people=len(fragmented),
        track_breaks=sum(len(person_tracks[person]) - 1 for person in matched),
        identity_switches=switches,
        impure_tracks=sum(1 for counter in track_people.values() if len(counter) > 1),
        duplicate_track_frames=duplicate_frames,
        track_labels=labels,
    )


@dataclass(frozen=True, slots=True)
class GalleryItem:
    key: str
    person_id: int | None
    camera: str
    frame: int
    box: Box
    embedding: tuple[float, ...]


@dataclass(frozen=True, slots=True)
class QueryOutcome:
    query_id: str
    mode: str
    person_id: int
    positives: int
    first_positive_rank: int | None
    top: tuple[tuple[str, int | None, float], ...]

    def hit(self, k: int) -> bool:
        return self.first_positive_rank is not None and self.first_positive_rank <= k

    def as_dict(self) -> dict[str, Any]:
        return {
            "query_id": self.query_id,
            "mode": self.mode,
            "person_id": self.person_id,
            "positives": self.positives,
            "first_positive_rank": self.first_positive_rank,
            "top": [
                {"key": key, "person_id": person, "score": round(score, 6)}
                for key, person, score in self.top
            ],
        }


def cosine(left: Sequence[float], right: Sequence[float]) -> float:
    if len(left) != len(right):
        raise ValueError("Embedding dimensions differ.")
    left_norm = math.sqrt(sum(value * value for value in left))
    right_norm = math.sqrt(sum(value * value for value in right))
    if not left_norm or not right_norm:
        raise ValueError("Embedding norm must be positive.")
    return sum(a * b for a, b in zip(left, right, strict=True)) / (left_norm * right_norm)


def rank_gallery(
    query_id: str,
    mode: str,
    person_id: int,
    embedding: Sequence[float],
    gallery: Iterable[GalleryItem],
    *,
    exclude: tuple[str, int, Box] | None = None,
    threshold: float = 0.5,
    keep_top: int = 16,
) -> QueryOutcome:
    candidates = []
    for item in gallery:
        if exclude is not None:
            camera, frame, box = exclude
            if item.camera == camera and item.frame == frame and iou(item.box, box) >= threshold:
                continue
        candidates.append((cosine(embedding, item.embedding), item))
    candidates.sort(key=lambda pair: (-pair[0], pair[1].key))
    positives = sum(1 for _, item in candidates if item.person_id == person_id)
    first = next(
        (rank for rank, (_, item) in enumerate(candidates, start=1) if item.person_id == person_id),
        None,
    )
    top = tuple((item.key, item.person_id, score) for score, item in candidates[:keep_top])
    return QueryOutcome(query_id, mode, person_id, positives, first, top)


def wilson_interval(successes: int, total: int, z: float = 1.96) -> tuple[float, float] | None:
    """Wilson score interval of a proportion; the usual choice for small samples."""

    if total <= 0:
        return None
    p = successes / total
    denominator = 1 + z * z / total
    centre = (p + z * z / (2 * total)) / denominator
    half = z * math.sqrt(p * (1 - p) / total + z * z / (4 * total * total)) / denominator
    return (round(max(0.0, centre - half), 4), round(min(1.0, centre + half), 4))


def recall_summary(
    outcomes: Iterable[QueryOutcome], ks: Sequence[int] = RECALL_KS
) -> dict[str, dict[str, Any]]:
    grouped: dict[str, list[QueryOutcome]] = defaultdict(list)
    for outcome in outcomes:
        grouped[outcome.mode].append(outcome)
    summary = {}
    for mode, items in sorted(grouped.items()):
        evaluable = [item for item in items if item.positives > 0]
        ranks = [item.first_positive_rank for item in evaluable if item.first_positive_rank]
        summary[mode] = {
            "queries": len(items),
            "evaluable_queries": len(evaluable),
            "queries_without_positive": sorted(
                item.query_id for item in items if item.positives == 0
            ),
            **{
                f"recall@{k}": _round(
                    sum(item.hit(k) for item in evaluable) / len(evaluable) if evaluable else None
                )
                for k in ks
            },
            **{
                f"recall@{k}_ci95": wilson_interval(
                    sum(item.hit(k) for item in evaluable), len(evaluable)
                )
                for k in ks
            },
            "mean_reciprocal_rank": _round(
                sum(1 / rank for rank in ranks) / len(evaluable) if evaluable else None
            ),
        }
    return summary


def _round(value: float | None) -> float | None:
    return None if value is None else round(value, 4)
