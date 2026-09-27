"""Deterministic inventory and verification for the local WILDTRACK dataset."""

from __future__ import annotations

import hashlib
import json
import re
from collections import Counter, defaultdict
from collections.abc import Callable
from fractions import Fraction
from pathlib import Path
from typing import Any

import av
from PIL import Image

from person_search.services.searches import attributes_prompt

MANIFEST_SCHEMA = "wildtrack-dataset-manifest/v1"
QUERY_SCHEMA = "wildtrack-evaluation-queries/v1"
EXPECTED_CAMERA_COUNT = 7
EXPECTED_FRAME_SIZE = (1920, 1080)
HASH_CHUNK_BYTES = 8 * 1024 * 1024


class WildtrackDatasetError(ValueError):
    """Raised when the local dataset is incomplete or structurally invalid."""


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(HASH_CHUNK_BYTES):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_sha256(value: Any) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _files(root: Path) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        if path.is_symlink():
            raise WildtrackDatasetError(f"Dataset file must not be a symlink: {path}")
        entries.append(
            {
                "path": path.relative_to(root).as_posix(),
                "size_bytes": path.stat().st_size,
                "sha256": sha256_file(path),
            }
        )
    entries.sort(key=lambda entry: entry["path"])
    return entries


def _video_metadata(path: Path) -> dict[str, Any]:
    try:
        with av.open(str(path)) as container:
            if not container.streams.video:
                raise WildtrackDatasetError(f"Video has no video stream: {path.name}")
            stream = container.streams.video[0]
            rate = Fraction(stream.average_rate) if stream.average_rate else None
            if stream.duration is not None and stream.time_base is not None:
                duration_seconds = float(stream.duration * stream.time_base)
            elif container.duration is not None:
                duration_seconds = float(container.duration / av.time_base)
            else:
                duration_seconds = None
            frame = next(container.decode(stream), None)
            if frame is None:
                raise WildtrackDatasetError(f"Video cannot decode its first frame: {path.name}")
            return {
                "container_format": container.format.name,
                "codec": stream.codec_context.name,
                "width": stream.codec_context.width,
                "height": stream.codec_context.height,
                "average_rate": (
                    {"numerator": rate.numerator, "denominator": rate.denominator}
                    if rate
                    else None
                ),
                "fps": round(float(rate), 6) if rate else None,
                "declared_frames": stream.frames or None,
                "duration_seconds": round(duration_seconds, 6) if duration_seconds else None,
                "time_base": str(stream.time_base) if stream.time_base else None,
                "first_frame": {
                    "width": frame.width,
                    "height": frame.height,
                    "pts": frame.pts,
                },
            }
    except (av.error.FFmpegError, OSError) as error:
        raise WildtrackDatasetError(f"Cannot inspect video {path.name}: {error}") from error


def _summarize_videos(
    root: Path,
    indexed_files: dict[str, dict[str, Any]],
    metadata_reader: Callable[[Path], dict[str, Any]],
) -> list[dict[str, Any]]:
    paths = sorted(root.glob("cam*.mp4"))
    if [path.name for path in paths] != [f"cam{index}.mp4" for index in range(1, 8)]:
        raise WildtrackDatasetError("Expected exactly cam1.mp4 through cam7.mp4.")
    videos = []
    for camera_number, path in enumerate(paths, start=1):
        relative = path.relative_to(root).as_posix()
        metadata = metadata_reader(path)
        videos.append(
            {
                "camera_number": camera_number,
                "logical_camera": f"C{camera_number}",
                "path": relative,
                "size_bytes": indexed_files[relative]["size_bytes"],
                "sha256": indexed_files[relative]["sha256"],
                **metadata,
            }
        )
    return videos


def _summarize_images(root: Path) -> dict[str, Any]:
    image_root = root / "Image_subsets"
    cameras = []
    for camera_number in range(1, EXPECTED_CAMERA_COUNT + 1):
        camera = f"C{camera_number}"
        paths = sorted((image_root / camera).glob("*.png"))
        if not paths:
            raise WildtrackDatasetError(f"No PNG frames found for {camera}.")
        dimensions: Counter[str] = Counter()
        modes: Counter[str] = Counter()
        total_bytes = 0
        for path in paths:
            total_bytes += path.stat().st_size
            try:
                with Image.open(path) as image:
                    dimensions[f"{image.width}x{image.height}"] += 1
                    modes[image.mode] += 1
            except OSError as error:
                raise WildtrackDatasetError(f"Cannot read image {path}: {error}") from error
        cameras.append(
            {
                "camera": camera,
                "count": len(paths),
                "first_frame": paths[0].stem,
                "last_frame": paths[-1].stem,
                "total_bytes": total_bytes,
                "dimensions": dict(sorted(dimensions.items())),
                "modes": dict(sorted(modes.items())),
            }
        )
    return {
        "camera_count": len(cameras),
        "total_images": sum(item["count"] for item in cameras),
        "cameras": cameras,
    }


def _bbox_state(view: dict[str, Any]) -> str:
    coordinates = tuple(view.get(key) for key in ("xmin", "ymin", "xmax", "ymax"))
    if coordinates == (-1, -1, -1, -1):
        return "absent"
    if any(type(value) is not int for value in coordinates):
        return "invalid"
    xmin, ymin, xmax, ymax = coordinates
    width, height = EXPECTED_FRAME_SIZE
    if xmin < xmax and ymin < ymax:
        if 0 <= xmin < xmax < width and 0 <= ymin < ymax < height:
            return "visible"
        if xmax >= 0 and ymax >= 0 and xmin < width and ymin < height:
            return "clip_required"
        return "outside_frame"
    return "invalid"


def _summarize_annotations(root: Path) -> dict[str, Any]:
    paths = sorted((root / "annotations_positions").glob("*.json"))
    if not paths:
        raise WildtrackDatasetError("No annotation JSON files found.")
    person_frames: dict[int, set[int]] = defaultdict(set)
    person_views: dict[int, Counter[int]] = defaultdict(Counter)
    visible_by_camera: Counter[int] = Counter()
    states: Counter[str] = Counter()
    observation_rows = 0
    position_ids: set[int] = set()
    frame_indices = []
    for path in paths:
        try:
            frame_index = int(path.stem)
            rows = json.loads(path.read_text(encoding="utf-8"))
        except (ValueError, json.JSONDecodeError) as error:
            raise WildtrackDatasetError(f"Invalid annotation file {path.name}.") from error
        if not isinstance(rows, list):
            raise WildtrackDatasetError(f"Annotation root must be a list: {path.name}")
        frame_indices.append(frame_index)
        for row in rows:
            if not isinstance(row, dict) or type(row.get("personID")) is not int:
                raise WildtrackDatasetError(f"Invalid person row in {path.name}.")
            views = row.get("views")
            if not isinstance(views, list) or len(views) != EXPECTED_CAMERA_COUNT:
                raise WildtrackDatasetError(f"Invalid views in {path.name}.")
            person_id = row["personID"]
            person_frames[person_id].add(frame_index)
            if type(row.get("positionID")) is int:
                position_ids.add(row["positionID"])
            observation_rows += 1
            seen_view_numbers = set()
            for view in views:
                view_number = view.get("viewNum") if isinstance(view, dict) else None
                if type(view_number) is not int or not 0 <= view_number < EXPECTED_CAMERA_COUNT:
                    raise WildtrackDatasetError(f"Invalid view number in {path.name}.")
                if view_number in seen_view_numbers:
                    raise WildtrackDatasetError(f"Duplicate view number in {path.name}.")
                seen_view_numbers.add(view_number)
                state = _bbox_state(view)
                states[state] += 1
                if state == "visible":
                    visible_by_camera[view_number] += 1
                    person_views[person_id][view_number] += 1
    identities = []
    for person_id in sorted(person_frames):
        frames = sorted(person_frames[person_id])
        views = person_views[person_id]
        identities.append(
            {
                "person_id": person_id,
                "annotated_frames": len(frames),
                "first_frame": frames[0],
                "last_frame": frames[-1],
                "visible_camera_count": len(views),
                "visible_observations": sum(views.values()),
                "visible_by_camera": {
                    f"C{view + 1}": count for view, count in sorted(views.items())
                },
            }
        )
    return {
        "file_count": len(paths),
        "first_frame": min(frame_indices),
        "last_frame": max(frame_indices),
        "frame_step_values": sorted(
            {right - left for left, right in zip(frame_indices, frame_indices[1:], strict=False)}
        ),
        "person_count": len(person_frames),
        "position_count": len(position_ids),
        "person_frame_rows": observation_rows,
        "view_box_states": dict(sorted(states.items())),
        "visible_boxes_by_camera": {
            f"C{view + 1}": visible_by_camera[view]
            for view in range(EXPECTED_CAMERA_COUNT)
        },
        "identities": identities,
    }


def build_manifest(
    dataset_root: str | Path,
    *,
    metadata_reader: Callable[[Path], dict[str, Any]] = _video_metadata,
) -> dict[str, Any]:
    root = Path(dataset_root).resolve()
    if not root.is_dir():
        raise WildtrackDatasetError(f"Dataset root does not exist: {root}")
    required = ("annotations_positions", "calibrations", "Image_subsets")
    missing = [name for name in required if not (root / name).is_dir()]
    if missing or not (root / "rectangles.pom").is_file():
        raise WildtrackDatasetError(f"Dataset is missing required entries: {missing}")

    files = _files(root)
    indexed_files = {entry["path"]: entry for entry in files}
    manifest: dict[str, Any] = {
        "schema": MANIFEST_SCHEMA,
        "dataset": "WILDTRACK local seven-camera dataset",
        "root_name": root.name,
        "content": {
            "file_count": len(files),
            "total_bytes": sum(entry["size_bytes"] for entry in files),
            "tree_sha256": canonical_sha256(files),
            "files": files,
        },
        "videos": _summarize_videos(root, indexed_files, metadata_reader),
        "image_subsets": _summarize_images(root),
        "annotations": _summarize_annotations(root),
        "calibrations": {
            "file_count": len(list((root / "calibrations").rglob("*.xml"))),
            "paths": sorted(
                path.relative_to(root).as_posix()
                for path in (root / "calibrations").rglob("*.xml")
            ),
        },
        "rectangles": indexed_files["rectangles.pom"],
    }
    manifest["manifest_sha256"] = canonical_sha256(manifest)
    return manifest


def write_manifest(manifest: dict[str, Any], output_path: str | Path) -> None:
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def verify_manifest(
    dataset_root: str | Path,
    manifest: dict[str, Any],
    *,
    metadata_reader: Callable[[Path], dict[str, Any]] = _video_metadata,
) -> list[str]:
    root = Path(dataset_root).resolve()
    errors: list[str] = []
    if manifest.get("schema") != MANIFEST_SCHEMA:
        errors.append("manifest schema mismatch")
    unsigned = {key: value for key, value in manifest.items() if key != "manifest_sha256"}
    if canonical_sha256(unsigned) != manifest.get("manifest_sha256"):
        errors.append("manifest_sha256 mismatch")

    expected_files = {
        entry["path"]: entry for entry in manifest.get("content", {}).get("files", [])
    }
    actual_paths = {
        path.relative_to(root).as_posix(): path
        for path in root.rglob("*")
        if path.is_file()
    }
    for missing in sorted(set(expected_files) - set(actual_paths)):
        errors.append(f"missing file: {missing}")
    for unexpected in sorted(set(actual_paths) - set(expected_files)):
        errors.append(f"unexpected file: {unexpected}")
    current_entries = []
    for relative in sorted(set(expected_files) & set(actual_paths)):
        path = actual_paths[relative]
        expected = expected_files[relative]
        size = path.stat().st_size
        digest = sha256_file(path)
        current_entries.append({"path": relative, "size_bytes": size, "sha256": digest})
        if size != expected.get("size_bytes"):
            errors.append(f"size mismatch: {relative}")
        if digest != expected.get("sha256"):
            errors.append(f"sha256 mismatch: {relative}")
    if canonical_sha256(current_entries) != manifest.get("content", {}).get("tree_sha256"):
        errors.append("tree_sha256 mismatch")

    expected_videos = {item["path"]: item for item in manifest.get("videos", [])}
    for relative, expected in expected_videos.items():
        path = root / relative
        if not path.is_file():
            continue
        current = metadata_reader(path)
        for field, value in current.items():
            if expected.get(field) != value:
                errors.append(f"video metadata mismatch: {relative}:{field}")
    return errors


def validate_query_set(dataset_root: str | Path, query_set: dict[str, Any]) -> list[str]:
    root = Path(dataset_root).resolve()
    errors: list[str] = []
    if query_set.get("schema") != QUERY_SCHEMA:
        errors.append("query schema mismatch")
    if query_set.get("language") != "en":
        errors.append("query language must be en")
    queries = query_set.get("queries")
    if not isinstance(queries, list) or not queries:
        return errors + ["queries must be a non-empty list"]

    seen_ids: set[str] = set()
    for query in queries:
        query_id = query.get("id") if isinstance(query, dict) else None
        prefix = str(query_id or "<missing-id>")
        if not isinstance(query_id, str) or not re.fullmatch(r"WT-Q\d{3}", query_id):
            errors.append(f"{prefix}: invalid query id")
        elif query_id in seen_ids:
            errors.append(f"{prefix}: duplicate query id")
        else:
            seen_ids.add(query_id)
        if not isinstance(query, dict) or type(query.get("person_id")) is not int:
            errors.append(f"{prefix}: invalid person_id")
            continue
        text = query.get("text_query")
        if not isinstance(text, str) or not text.strip() or not text.isascii():
            errors.append(f"{prefix}: text_query must be non-empty ASCII English text")

        attributes = query.get("attribute_query")
        if not isinstance(attributes, dict) or not attributes:
            errors.append(f"{prefix}: attribute_query must be a non-empty object")
        else:
            # Same vocabulary and rules as the Operator attribute search.
            try:
                attributes_prompt(attributes)
            except ValueError as error:
                errors.append(f"{prefix}: {error}")

        image_query = query.get("image_query")
        if not isinstance(image_query, dict):
            errors.append(f"{prefix}: image_query must be an object")
            continue
        camera = image_query.get("camera")
        frame = image_query.get("frame")
        relative = image_query.get("path")
        bbox = image_query.get("bbox")
        if not isinstance(camera, str) or not re.fullmatch(r"C[1-7]", camera):
            errors.append(f"{prefix}: invalid camera")
            continue
        if not isinstance(frame, str) or not re.fullmatch(r"\d{8}", frame):
            errors.append(f"{prefix}: invalid frame")
            continue
        expected_relative = f"Image_subsets/{camera}/{frame}.png"
        if relative != expected_relative:
            errors.append(f"{prefix}: image path does not match camera/frame")
            continue
        image_path = root.joinpath(*expected_relative.split("/"))
        if not image_path.is_file():
            errors.append(f"{prefix}: image file is missing")
            continue
        keys = ("xmin", "ymin", "xmax", "ymax")
        if not isinstance(bbox, dict) or any(type(bbox.get(key)) is not int for key in keys):
            errors.append(f"{prefix}: invalid bbox")
            continue
        with Image.open(image_path) as image:
            xmin, ymin, xmax, ymax = (bbox[key] for key in keys)
            if not (0 <= xmin < xmax < image.width and 0 <= ymin < ymax < image.height):
                errors.append(f"{prefix}: bbox is outside the image")
                continue
        annotation_path = root / "annotations_positions" / f"{frame}.json"
        if not annotation_path.is_file():
            errors.append(f"{prefix}: annotation file is missing")
            continue
        rows = json.loads(annotation_path.read_text(encoding="utf-8"))
        person = next(
            (row for row in rows if row.get("personID") == query["person_id"]), None
        )
        if person is None:
            errors.append(f"{prefix}: person_id is absent from annotation")
            continue
        view_number = int(camera[1:]) - 1
        view = next(
            (
                item
                for item in person.get("views", [])
                if item.get("viewNum") == view_number
            ),
            None,
        )
        expected_bbox = {key: view.get(key) for key in keys} if view else None
        if bbox != expected_bbox:
            errors.append(f"{prefix}: bbox does not match annotation")
    return errors
