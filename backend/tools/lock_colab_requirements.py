from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
PROJECT_NAME = "person-search-backend"


def lock_lines(report: dict) -> list[str]:
    lines = []
    for item in report["install"]:
        metadata = item["metadata"]
        name = metadata["name"].lower()
        if name == PROJECT_NAME:
            continue
        digest = item["download_info"].get("archive_info", {}).get("hashes", {}).get("sha256")
        if not digest:
            raise ValueError(f"{name} has no sha256 in the resolver report")
        lines.append(f"{name}=={metadata['version']} --hash=sha256:{digest}")
    return sorted(lines)


def resolve(extras: str, python_version: str, platforms: list[str]) -> dict:
    with tempfile.TemporaryDirectory() as directory:
        report = Path(directory) / "report.json"
        command = [
            sys.executable,
            "-m",
            "pip",
            "install",
            "--dry-run",
            "--quiet",
            "--ignore-installed",
            "--only-binary=:all:",
            "--implementation",
            "cp",
            "--python-version",
            python_version,
            "--target",
            str(Path(directory) / "target"),
            "--report",
            str(report),
        ]
        for platform in platforms:
            command += ["--platform", platform]
        command.append(f"{BACKEND}[{extras}]")
        subprocess.run(command, check=True)
        return json.loads(report.read_text(encoding="utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Resolve a hash-pinned Linux x86_64 lock for the Colab batch runtime."
    )
    parser.add_argument("--extras", default="ai-ultralytics,ai-rasa")
    parser.add_argument("--python-version", default="3.12")
    parser.add_argument(
        "--platform",
        action="append",
        default=None,
        help="Wheel platform tag; defaults to manylinux_2_28_x86_64 and manylinux2014_x86_64.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=BACKEND / "requirements" / "colab-linux-x86_64-cp312.lock.txt",
    )
    args = parser.parse_args()
    platforms = args.platform or ["manylinux_2_28_x86_64", "manylinux2014_x86_64"]
    lines = lock_lines(resolve(args.extras, args.python_version, platforms))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(args.output), "packages": len(lines)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
