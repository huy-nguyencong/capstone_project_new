import json
from pathlib import Path

import pytest
from PIL import Image

from person_search.datasets.wildtrack import build_manifest, validate_query_set, verify_manifest

pytestmark = pytest.mark.unit


def _video_metadata(path: Path):
    return {
        "container_format": "fixture",
        "codec": "fixture",
        "width": 1920,
        "height": 1080,
        "average_rate": {"numerator": 60, "denominator": 1},
        "fps": 60.0,
        "declared_frames": 1,
        "duration_seconds": 1.0,
        "time_base": "1/60",
        "first_frame": {"width": 1920, "height": 1080, "pts": 0},
    }


def _dataset(root: Path) -> None:
    (root / "annotations_positions").mkdir(parents=True)
    (root / "calibrations" / "extrinsic").mkdir(parents=True)
    (root / "calibrations" / "extrinsic" / "camera.xml").write_text("<xml />")
    (root / "rectangles.pom").write_bytes(b"rectangles")
    views = []
    for view in range(7):
        camera = root / "Image_subsets" / f"C{view + 1}"
        camera.mkdir(parents=True)
        Image.new("RGB", (1920, 1080), "black").save(camera / "00000000.png")
        views.append(
            {
                "viewNum": view,
                "xmin": 10 if view == 0 else -1,
                "ymin": 20 if view == 0 else -1,
                "xmax": 30 if view == 0 else -1,
                "ymax": 60 if view == 0 else -1,
            }
        )
    (root / "annotations_positions" / "00000000.json").write_text(
        json.dumps([{"personID": 7, "positionID": 11, "views": views}])
    )
    for index in range(1, 8):
        (root / f"cam{index}.mp4").write_bytes(f"video-{index}".encode())


def test_build_and_verify_manifest_detects_content_changes(tmp_path):
    root = tmp_path / "wildtrack"
    _dataset(root)

    manifest = build_manifest(root, metadata_reader=_video_metadata)

    assert manifest["schema"] == "wildtrack-dataset-manifest/v1"
    assert len(manifest["videos"]) == 7
    assert manifest["image_subsets"]["total_images"] == 7
    assert manifest["annotations"]["person_count"] == 1
    assert manifest["annotations"]["view_box_states"] == {"absent": 6, "visible": 1}
    assert verify_manifest(root, manifest, metadata_reader=_video_metadata) == []

    (root / "rectangles.pom").write_bytes(b"changed")
    errors = verify_manifest(root, manifest, metadata_reader=_video_metadata)
    assert "sha256 mismatch: rectangles.pom" in errors
    assert "tree_sha256 mismatch" in errors


def test_validate_query_set_requires_matching_annotation(tmp_path):
    root = tmp_path / "wildtrack"
    _dataset(root)
    query = {
        "schema": "wildtrack-evaluation-queries/v1",
        "language": "en",
        "queries": [
            {
                "id": "WT-Q001",
                "person_id": 7,
                "image_query": {
                    "camera": "C1",
                    "frame": "00000000",
                    "path": "Image_subsets/C1/00000000.png",
                    "bbox": {"xmin": 10, "ymin": 20, "xmax": 30, "ymax": 60},
                },
                "text_query": "A person wearing a black jacket.",
                "attribute_query": {"upper_color": "black", "upper_type": "jacket"},
            }
        ],
    }

    assert validate_query_set(root, query) == []
    query["queries"][0]["image_query"]["bbox"]["xmax"] = 31
    assert validate_query_set(root, query) == ["WT-Q001: bbox does not match annotation"]
