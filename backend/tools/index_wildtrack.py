"""Index WILDTRACK clips for the demo through the running API and worker (video upload path).

Cameras ``WT-CAM1..7`` are created once in area ``GATE-A`` and reused, with AI processing enabled.
Each run cuts ``--seconds`` of every selected view starting at ``--start`` (FFmpeg stream copy),
uploads it as a processing job and waits until every job ends. The seven views are synchronized,
so all clips share one timeline origin: a clip starting at ``--start`` is recorded at
``--origin + start``, and the same moment has the same time on every camera.

Needs the API (``python -m person_search``) and ``person-search-production-worker`` running, FFmpeg
in PATH and an Admin account. Uses the active Detector/Tracker; ``--baseline`` first switches the
system to YOLO11n + ByteTrack (the configuration the demo data was built with).

    python tools/index_wildtrack.py --start 60 --seconds 60
    python tools/index_wildtrack.py --cams 1 2 --start 0 --seconds 60 --baseline
"""

from __future__ import annotations

import argparse
import getpass
import http.cookiejar
import json
import mimetypes
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

REPOSITORY = Path(__file__).resolve().parents[2]
TERMINAL = {"SUCCEEDED", "FAILED", "CANCELLED"}
BASELINE = ("yolo11n_coco", "bytetrack_v1")


class Api:
    """Minimal session client: cookie session, CSRF header and JSON/multipart bodies."""

    def __init__(self, base_url: str) -> None:
        self.base_url = base_url.rstrip("/")
        self.opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar())
        )
        self.csrf: str | None = None

    def call(self, method, path, *, body=None, files=None, fields=None, headers=None, timeout=600):
        headers = dict(headers or {})
        data = None
        if files is not None:
            boundary = uuid.uuid4().hex
            data = _multipart(boundary, fields or {}, files)
            headers["Content-Type"] = f"multipart/form-data; boundary={boundary}"
        elif body is not None:
            data = json.dumps(body).encode()
            headers["Content-Type"] = "application/json"
        if self.csrf and method != "GET":
            headers["X-CSRF-Token"] = self.csrf
        request = urllib.request.Request(
            f"{self.base_url}{path}", data=data, method=method, headers=headers
        )
        try:
            with self.opener.open(request, timeout=timeout) as response:
                return json.loads(response.read() or b"null")
        except urllib.error.HTTPError as error:
            sys.exit(
                f"{method} {path} -> {error.code} {error.read()[:400].decode(errors='replace')}"
            )


def _content_type(path: Path) -> str:
    return mimetypes.guess_type(path.name)[0] or "application/octet-stream"


def _multipart(boundary: str, fields: dict[str, str], files: dict[str, Path]) -> bytes:
    parts = []
    for name, value in fields.items():
        header = f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"\r\n\r\n'
        parts.append(f"{header}{value}\r\n".encode())
    for name, path in files.items():
        parts.append(
            (
                f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"; '
                f'filename="{path.name}"\r\nContent-Type: {_content_type(path)}\r\n\r\n'
            ).encode()
            + path.read_bytes()
            + b"\r\n"
        )
    return b"".join(parts) + f"--{boundary}--\r\n".encode()


def _items(value):
    return value["items"] if isinstance(value, dict) else value


def _cut_clip(dataset: Path, clips: Path, camera: int, start: int, seconds: int) -> Path:
    clip = clips / f"cam{camera}_{start}s_{seconds}s.mp4"
    if not clip.exists():
        subprocess.run(
            [
                "ffmpeg", "-v", "error", "-y", "-ss", str(start),
                "-i", str(dataset / f"cam{camera}.mp4"), "-t", str(seconds),
                "-c", "copy", str(clip),
            ],
            check=True,
        )  # fmt: skip
    return clip


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--cams", type=int, nargs="+", default=list(range(1, 8)))
    parser.add_argument("--start", type=int, default=0, help="clip start in seconds")
    parser.add_argument("--seconds", type=int, default=60)
    parser.add_argument("--profile", default="throughput", help="sampling profile of the job")
    parser.add_argument(
        "--origin",
        default="2026-09-27T08:00:00+00:00",
        help="recorded time of second 0 of every view (UTC ISO 8601)",
    )
    parser.add_argument("--baseline", action="store_true", help="switch to YOLO11n + ByteTrack")
    parser.add_argument(
        "--api", default=os.getenv("PERSON_SEARCH_API", "http://127.0.0.1:5000/api/v1")
    )
    parser.add_argument("--username", default="admin")
    parser.add_argument("--dataset", type=Path, default=REPOSITORY / "wildtrack-dataset")
    parser.add_argument("--clips", type=Path, default=REPOSITORY / "backend" / "var" / "clips")
    args = parser.parse_args()

    password = os.getenv("PERSON_SEARCH_ADMIN_PASSWORD") or getpass.getpass("Admin password: ")
    origin = datetime.fromisoformat(args.origin).astimezone(UTC)
    api = Api(args.api)
    login = api.call("POST", "/auth/login", body={"username": args.username, "password": password})
    api.csrf = login["csrf_token"]

    config = api.call("GET", "/admin/ai/config")
    if args.baseline and (config["detector_id"], config["tracker_id"]) != BASELINE:
        api.call(
            "PUT",
            "/admin/ai/config",
            body={
                "detector_id": BASELINE[0],
                "tracker_id": BASELINE[1],
                "version": config["version"],
            },
        )
        config = api.call("GET", "/admin/ai/config")
    print(f"AI config: {config['detector_id']} + {config['tracker_id']}", flush=True)

    gate = next(area for area in _items(api.call("GET", "/areas")) if area["code"] == "GATE-A")
    existing = {
        camera["code"]: camera for camera in _items(api.call("GET", "/admin/cameras?limit=100"))
    }
    args.clips.mkdir(parents=True, exist_ok=True)
    jobs = []
    for number in args.cams:
        code = f"WT-CAM{number}"
        camera = existing.get(code) or api.call(
            "POST",
            "/admin/cameras",
            body={"code": code, "name": f"WILDTRACK Cam {number}", "area_id": gate["id"]},
        )
        if camera["status"] != "ACTIVE":
            sys.exit(f"{code} is {camera['status']}; return it to operation first.")
        if not camera["ai_enabled"]:
            api.call("PUT", f"/admin/cameras/{camera['id']}/ai-state", body={"enabled": True})
        clip = _cut_clip(args.dataset, args.clips, number, args.start, args.seconds)
        job = api.call(
            "POST",
            f"/admin/cameras/{camera['id']}/processing-jobs",
            files={"file": clip},
            fields={
                "recorded_started_at": (origin + timedelta(seconds=args.start)).isoformat(),
                "sampling_profile": args.profile,
            },
            headers={"Idempotency-Key": str(uuid.uuid4())},
        )
        print(f"queued {code}: job {job['id']} ({clip.stat().st_size // 2**20} MB)", flush=True)
        jobs.append((code, job["id"]))

    started = time.time()
    failed = 0
    for code, job_id in jobs:
        while True:
            job = api.call("GET", f"/admin/processing-jobs/{job_id}")
            if job["status"] in TERMINAL:
                break
            time.sleep(10)
        failed += job["status"] != "SUCCEEDED"
        print(
            f"{code}: {job['status']} at {time.time() - started:.0f}s | "
            f"frames {job['processed_frames']}/{job['total_frames']} "
            f"sampled {job['sampled_frames']} tracks ready {job['tracks_ready']} "
            f"failed {job['tracks_failed']} error {job['error_code']}",
            flush=True,
        )
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
