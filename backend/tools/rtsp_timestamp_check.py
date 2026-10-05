"""Compare stream-clock and machine-clock timestamps of an RTSP stream under slow processing.

The tool reads frames from the RTSP URL given on the command line through the production
``RtspFrameSource``, once per timestamp mode, and emulates a slow analysis pipeline by sleeping
``--slow-ms`` after every frame (0 = as fast as the decoder allows). For every ``--sampling``-th
frame it records the gap between consecutive sampled frames according to the frame timestamps and
according to the wall clock. With the machine clock, the gap grows with the processing time and
can exceed the two-second track termination rule; with the stream clock, it stays at the stream's
own frame spacing.

    python tools/rtsp_timestamp_check.py --url rtsp://192.168.110.148:8554/cam1 --frames 300 \
        --sampling 20 --slow-ms 100 --output var/evidence/rtsp-timestamps.json
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
import uuid
from datetime import UTC, datetime
from pathlib import Path

from person_search.workers.sources import RtspFrameSource


def _run(url: str, *, mode: str, frames: int, sampling: int, slow_ms: float) -> dict:
    # Measurement tool: it only talks to the URL given on the command line, so the deployment
    # network policy of the worker is not applied here.
    source = RtspFrameSource(
        access_resolver=lambda public_url, secret: public_url,
        timestamp_mode=mode,
        max_reconnects=1,
    ).open(url, camera_id=uuid.uuid4())
    stamp_gaps, wall_gaps = [], []
    last_stamp = last_wall = None
    started = time.perf_counter()
    first_stamp = None
    with source:
        for frame in source:
            if first_stamp is None:
                first_stamp = frame.source_timestamp_ms
            if frame.source_frame_index % sampling == 0:
                now = time.perf_counter()
                if last_stamp is not None:
                    stamp_gaps.append(frame.source_timestamp_ms - last_stamp)
                    wall_gaps.append(round((now - last_wall) * 1000))
                last_stamp, last_wall = frame.source_timestamp_ms, now
            if slow_ms > 0:
                time.sleep(slow_ms / 1000)
            if frame.source_frame_index + 1 >= frames:
                break
            last_frame = frame
    elapsed = time.perf_counter() - started

    def summary(values):
        if not values:
            return None
        return {
            "n": len(values),
            "mean_ms": round(statistics.fmean(values), 1),
            "median_ms": round(statistics.median(values), 1),
            "max_ms": max(values),
            "over_2000_ms": sum(1 for value in values if value > 2000),
        }

    return {
        "timestamp_mode": mode,
        "frames_read": frames,
        "sampling_interval": sampling,
        "slow_ms_per_frame": slow_ms,
        "elapsed_seconds": round(elapsed, 1),
        "stream_seconds_covered": round((last_frame.source_timestamp_ms - first_stamp) / 1000, 2),
        "gap_between_sampled_frames_by_timestamp": summary(stamp_gaps),
        "gap_between_sampled_frames_by_wall_clock": summary(wall_gaps),
        "timeline_anchors": source.timeline_anchors,
        "timestamp_fallback_frames": source.timestamp_fallback_frames,
        "reconnects": source.reconnects,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--url", required=True)
    parser.add_argument("--frames", type=int, default=300)
    parser.add_argument("--sampling", type=int, default=20)
    parser.add_argument("--slow-ms", type=float, default=0.0)
    parser.add_argument("--modes", default="clock,stream")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    runs = []
    for mode in [item.strip() for item in args.modes.split(",") if item.strip()]:
        print(
            f"[{mode}] reading {args.frames} frames, sampling 1/{args.sampling},"
            f" {args.slow_ms} ms per frame"
        )
        run = _run(
            args.url, mode=mode, frames=args.frames, sampling=args.sampling, slow_ms=args.slow_ms
        )
        runs.append(run)
        by_stamp = run["gap_between_sampled_frames_by_timestamp"]
        by_wall = run["gap_between_sampled_frames_by_wall_clock"]
        print(
            f"    gap by timestamp: median {by_stamp['median_ms']} ms, max {by_stamp['max_ms']} ms,"
            f" >2 s: {by_stamp['over_2000_ms']} of {by_stamp['n']};"
            f" by wall clock: median {by_wall['median_ms']} ms;"
            f" stream covered {run['stream_seconds_covered']} s in {run['elapsed_seconds']} s;"
            f" fallback frames {run['timestamp_fallback_frames']},"
            f" anchors {run['timeline_anchors']}"
        )
    report = {
        "schema": "person-search-rtsp-timestamps/v1",
        "measured_at": datetime.now(UTC).isoformat(),
        "python": sys.version.split()[0],
        "url_host": args.url.split("@")[-1].split("/")[2] if "//" in args.url else None,
        "runs": runs,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"written {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
