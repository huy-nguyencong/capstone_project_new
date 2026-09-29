"""Measure end-to-end search latency (client side) through the running API.

Logs in as an Operator, warms each search mode up once, then calls the image, text and attribute
search endpoints ``--runs`` times each (interleaved), timing every request on the client. Search is
read-only. The API allows 30 searches per minute per account, so calls are spaced by
``--spacing`` seconds; any 429 response is recorded and excluded from the statistics.

    python tools/benchmark_search_latency.py --output var/benchmark/search-latency.json

Password: ``PERSON_SEARCH_OPERATOR_PASSWORD`` or prompted.
"""

from __future__ import annotations

import argparse
import getpass
import json
import math
import os
import platform
import subprocess
import sys
import time
import urllib.error
import urllib.request
import uuid
from datetime import UTC, datetime
from pathlib import Path

from index_wildtrack import Api, _multipart

REPOSITORY = Path(__file__).resolve().parents[2]
DEFAULT_TEXT = "a man wearing a black jacket and blue jeans"
DEFAULT_ATTRIBUTES = {
    "upper_type": "jacket",
    "upper_color": "black",
    "lower_type": "jeans",
    "lower_color": "blue",
}


def _percentile(values: list[float], fraction: float) -> float:
    """Nearest-rank percentile."""

    ordered = sorted(values)
    rank = min(len(ordered), max(1, math.ceil(fraction * len(ordered))))
    return ordered[rank - 1]


def _stats(values: list[float]) -> dict[str, float] | None:
    if not values:
        return None
    return {
        "n": len(values),
        "p50_ms": round(_percentile(values, 0.50), 1),
        "p95_ms": round(_percentile(values, 0.95), 1),
        "max_ms": round(max(values), 1),
        "min_ms": round(min(values), 1),
        "mean_ms": round(sum(values) / len(values), 1),
    }


def _request(api: Api, mode: str, args: argparse.Namespace) -> tuple[int, float, int]:
    """Return (HTTP status, elapsed ms, result count) for one search call."""

    headers = {"X-CSRF-Token": api.csrf}
    if mode == "image":
        boundary = uuid.uuid4().hex
        data = _multipart(boundary, {"top_k": str(args.top_k)}, {"image": args.image})
        headers["Content-Type"] = f"multipart/form-data; boundary={boundary}"
    else:
        body = {"top_k": args.top_k}
        body |= {"text": args.text} if mode == "text" else {"attributes": args.attributes}
        data = json.dumps(body).encode()
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(
        f"{api.base_url}/searches/{mode}", data=data, method="POST", headers=headers
    )
    started = time.perf_counter()
    try:
        with api.opener.open(request, timeout=300) as response:
            payload = json.loads(response.read())
            status = response.status
    except urllib.error.HTTPError as error:
        error.read()
        return error.code, (time.perf_counter() - started) * 1000, 0
    return status, (time.perf_counter() - started) * 1000, len(payload.get("results", []))


def _git_commit() -> str | None:
    try:
        return subprocess.run(
            ["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=True
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument(
        "--api", default=os.getenv("PERSON_SEARCH_API", "http://127.0.0.1:5000/api/v1")
    )
    parser.add_argument("--username", default="operator")
    parser.add_argument("--runs", type=int, default=30)
    parser.add_argument("--top-k", type=int, default=8)
    parser.add_argument("--spacing", type=float, default=2.5, help="seconds between calls")
    parser.add_argument(
        "--image",
        type=Path,
        default=REPOSITORY / "backend" / "var" / "demo-queries" / "WT-Q006.jpg",
    )
    parser.add_argument("--text", default=DEFAULT_TEXT)
    parser.add_argument("--attributes", type=json.loads, default=DEFAULT_ATTRIBUTES)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if not args.image.is_file():
        sys.exit(f"Query image not found: {args.image}")

    password = os.getenv("PERSON_SEARCH_OPERATOR_PASSWORD") or getpass.getpass("Password: ")
    api = Api(args.api)
    api.csrf = api.call(
        "POST", "/auth/login", body={"username": args.username, "password": password}
    )["csrf_token"]
    modes = ("image", "text", "attribute")
    endpoint = {"image": "image", "text": "text", "attribute": "attributes"}

    warmup = {}
    for mode in modes:
        status, elapsed, count = _request(api, endpoint[mode], args)
        warmup[mode] = {"status": status, "ms": round(elapsed, 1), "results": count}
        print(f"warm-up {mode}: {status} {elapsed:.0f} ms", flush=True)
        time.sleep(args.spacing)

    calls = []
    for index in range(args.runs):
        for mode in modes:
            status, elapsed, count = _request(api, endpoint[mode], args)
            calls.append(
                {
                    "mode": mode,
                    "run": index + 1,
                    "status": status,
                    "ms": round(elapsed, 1),
                    "results": count,
                }
            )
            if status == 429:
                print(f"{mode} #{index + 1}: 429, excluded", flush=True)
            time.sleep(args.spacing)
        print(f"round {index + 1}/{args.runs} done", flush=True)

    summary = {}
    for mode in modes:
        ok = [call["ms"] for call in calls if call["mode"] == mode and call["status"] == 200]
        summary[mode] = {
            "latency": _stats(ok),
            "rate_limited": sum(1 for c in calls if c["mode"] == mode and c["status"] == 429),
            "other_errors": sorted(
                {c["status"] for c in calls if c["mode"] == mode and c["status"] not in (200, 429)}
            ),
        }
    report = {
        "schema": "person-search-search-latency/v1",
        "measured_at": datetime.now(UTC).isoformat(),
        "git_commit": _git_commit(),
        "machine": {"platform": platform.platform(), "processor": platform.processor()},
        "settings": {
            "api": args.api,
            "username": args.username,
            "runs_per_mode": args.runs,
            "top_k": args.top_k,
            "spacing_seconds": args.spacing,
            "image": args.image.name,
            "text": args.text,
            "attributes": args.attributes,
            "timing": "client side, full HTTP request incl. encoder, vector search and hydration",
        },
        "warmup": warmup,
        "summary": summary,
        "calls": calls,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
