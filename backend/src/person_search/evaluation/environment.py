from __future__ import annotations

import hashlib
import os
import platform
import shutil
import subprocess
from collections.abc import Callable, Mapping
from importlib import metadata
from pathlib import Path
from typing import Any

PACKAGES = (
    "torch",
    "torchvision",
    "ultralytics",
    "lap",
    "transformers",
    "timm",
    "av",
    "Pillow",
    "numpy",
)


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def run_command(command: list[str]) -> str | None:
    if shutil.which(command[0]) is None:
        return None
    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=10, check=False)
    except (OSError, subprocess.TimeoutExpired):
        return None
    return result.stdout.strip() if result.returncode == 0 else None


def package_versions(packages: tuple[str, ...] = PACKAGES) -> dict[str, str | None]:
    versions: dict[str, str | None] = {}
    for name in packages:
        try:
            versions[name] = metadata.version(name)
        except metadata.PackageNotFoundError:
            versions[name] = None
    return versions


def total_memory_bytes() -> int | None:
    try:
        return os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES")
    except (ValueError, OSError, AttributeError):
        return None


def gpu_snapshot(runner: Callable[[list[str]], str | None] = run_command) -> list[dict[str, str]]:
    output = runner(
        [
            "nvidia-smi",
            "--query-gpu=name,memory.total,driver_version,compute_mode",
            "--format=csv,noheader",
        ]
    )
    if not output:
        return []
    rows = []
    for line in output.splitlines():
        parts = [part.strip() for part in line.split(",")]
        if len(parts) == 4:
            rows.append(
                {
                    "name": parts[0],
                    "memory_total": parts[1],
                    "driver": parts[2],
                    "compute_mode": parts[3],
                }
            )
    return rows


def environment_snapshot(
    repository: Path | None = None,
    *,
    runner: Callable[[list[str]], str | None] = run_command,
    extra: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    root = repository or Path(__file__).resolve().parents[4]
    commit = runner(["git", "-C", str(root), "rev-parse", "HEAD"])
    dirty = runner(["git", "-C", str(root), "status", "--porcelain"])
    ffmpeg = runner(["ffmpeg", "-version"])
    snapshot = {
        "python": platform.python_version(),
        "platform": platform.platform(),
        "machine": platform.machine(),
        "processor": platform.processor() or None,
        "cpu_count": os.cpu_count(),
        "memory_total_bytes": total_memory_bytes(),
        "gpus": gpu_snapshot(runner),
        "packages": package_versions(),
        "ffmpeg": ffmpeg.splitlines()[0] if ffmpeg else None,
        "git_commit": commit,
        "git_dirty": bool(dirty) if dirty is not None else None,
        "colab": "COLAB_RELEASE_TAG" in os.environ or "COLAB_GPU" in os.environ,
    }
    if extra:
        snapshot.update(extra)
    return snapshot


def registry_lineage(registry: Any, detector_id: str, tracker_id: str) -> dict[str, Any]:
    selection = registry.resolve(detector_id, tracker_id)
    return {
        component: {
            "id": entry.id,
            "version": entry.version,
            "artifact_sha256": entry.artifact.sha256,
        }
        for component, entry in (
            ("detector", selection.detector),
            ("tracker", selection.tracker),
            ("encoder", selection.encoder),
        )
    }


def settings_lineage(paths: Mapping[str, Path]) -> dict[str, dict[str, str]]:
    return {
        name: {"path": path.name, "sha256": file_sha256(path)} for name, path in paths.items()
    }
