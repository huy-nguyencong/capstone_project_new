from __future__ import annotations

import argparse
import json
import os
import subprocess
from pathlib import Path

from dotenv import load_dotenv

from person_search.release import (
    disk_checks,
    environment_checks,
    git_checks,
    registry_checks,
    summarize,
)
from person_search.services.cameras import CameraService

REPOSITORY = Path(__file__).resolve().parents[2]


def tracked_files() -> list[str] | None:
    try:
        result = subprocess.run(
            ["git", "-C", str(REPOSITORY), "ls-files"],
            capture_output=True,
            text=True,
            timeout=30,
            check=True,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return result.stdout.splitlines()


def tracked_size(path: str) -> int | None:
    target = REPOSITORY / path
    return target.stat().st_size if target.is_file() else None


def main() -> int:
    load_dotenv()
    parser = argparse.ArgumentParser(
        description="Pre-demo checklist: environment, secrets, registry, licenses, git, disk."
    )
    parser.add_argument("--detector", default="yolo11n_coco")
    parser.add_argument("--tracker", default="bytetrack_v1")
    parser.add_argument("--min-free-gb", type=float, default=20.0)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    staging = Path(os.getenv("PERSON_SEARCH_VIDEO_STAGING", "var/videos")).resolve()
    checks = [
        *environment_checks(os.environ),
        *registry_checks(
            lambda: CameraService.registry_from_environment("production"),
            args.detector,
            args.tracker,
        ),
        *git_checks(tracked_files(), size_of=tracked_size),
        *disk_checks(staging, int(args.min_free_gb * 1024**3)),
    ]
    report = summarize(checks)
    text = json.dumps(report, indent=2, ensure_ascii=False)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
    print(text)
    return 0 if report["ready"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
