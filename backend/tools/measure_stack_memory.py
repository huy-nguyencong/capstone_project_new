"""Sample memory of the whole demo stack in one named state and keep the maximum per item.

Records ``docker stats`` memory of every person-search container, the resident memory (RSS,
working set on Windows) of each application process group (API, worker, AI pipeline, frontend,
RTSP publishers, Docker VM) including child processes, and the machine's used memory. Each state
is sampled ``--samples`` times, ``--interval`` seconds apart; the report keeps the maximum.
Results for several states accumulate in one JSON file.

    python tools/measure_stack_memory.py --state idle --output var/benchmark/stack-memory.json
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import time
from datetime import UTC, datetime
from pathlib import Path

import psutil

UNITS = {"B": 1, "KIB": 2**10, "MIB": 2**20, "GIB": 2**30, "KB": 10**3, "MB": 10**6, "GB": 10**9}

# Group name -> predicate on (process name, command line).
GROUPS = {
    "api": lambda name, cmd: re.search(r"-m person_search(\s|$)", cmd) is not None,
    "worker": lambda name, cmd: (
        "person-search-production-worker" in cmd or "person_search.workers" in cmd
    ),
    "ai_pipeline_benchmark": lambda name, cmd: "benchmark_sampling.py" in cmd,
    "frontend_vite": lambda name, cmd: name.lower().startswith("node") and "vite" in cmd,
    "rtsp_publishers": lambda name, cmd: name.lower().startswith("ffmpeg") and "rtsp://" in cmd,
    "docker_vm": lambda name, cmd: name.lower().startswith("vmmem"),
}


def _bytes(text: str) -> int:
    match = re.match(r"([\d.]+)\s*([A-Za-z]+)", text.strip())
    if not match:
        return 0
    return int(float(match.group(1)) * UNITS.get(match.group(2).upper(), 1))


def _containers() -> dict[str, int]:
    output = subprocess.run(
        ["docker", "stats", "--no-stream", "--format", "{{json .}}"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    usage = {}
    for line in output.splitlines():
        row = json.loads(line)
        if "person-search" in row["Name"]:
            usage[row["Name"]] = _bytes(row["MemUsage"].split("/")[0])
    return usage


def _process_groups() -> dict[str, dict[str, int]]:
    roots: dict[str, set[int]] = {group: set() for group in GROUPS}
    for process in psutil.process_iter(["pid", "name", "cmdline"]):
        try:
            name = process.info["name"] or ""
            cmd = " ".join(process.info["cmdline"] or [])
        except (psutil.Error, TypeError):
            continue
        for group, matches in GROUPS.items():
            if matches(name, cmd):
                roots[group].add(process.info["pid"])
    groups = {}
    for group, pids in roots.items():
        members: set[int] = set()
        for pid in pids:
            try:
                members.add(pid)
                members.update(child.pid for child in psutil.Process(pid).children(recursive=True))
            except psutil.Error:
                continue
        rss = 0
        for pid in members:
            try:
                rss += psutil.Process(pid).memory_info().rss
            except psutil.Error:
                continue
        groups[group] = {"processes": len(members), "rss_bytes": rss}
    return groups


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--state", required=True, help="label, e.g. idle, processing, searching")
    parser.add_argument("--samples", type=int, default=5)
    parser.add_argument("--interval", type=float, default=2.0)
    parser.add_argument("--note", default="")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    peak_containers: dict[str, int] = {}
    peak_groups: dict[str, dict[str, int]] = {}
    peak_used = 0
    for index in range(args.samples):
        for name, value in _containers().items():
            peak_containers[name] = max(value, peak_containers.get(name, 0))
        for group, value in _process_groups().items():
            best = peak_groups.setdefault(group, {"processes": 0, "rss_bytes": 0})
            best["processes"] = max(best["processes"], value["processes"])
            best["rss_bytes"] = max(best["rss_bytes"], value["rss_bytes"])
        peak_used = max(peak_used, psutil.virtual_memory().used)
        if index + 1 < args.samples:
            time.sleep(args.interval)

    memory = psutil.virtual_memory()
    state = {
        "measured_at": datetime.now(UTC).isoformat(),
        "samples": args.samples,
        "interval_seconds": args.interval,
        "note": args.note,
        "containers_bytes": dict(sorted(peak_containers.items())),
        "containers_total_bytes": sum(peak_containers.values()),
        "process_groups": peak_groups,
        "machine": {
            "total_bytes": memory.total,
            "used_bytes_max": peak_used,
            "available_bytes_at_end": memory.available,
        },
    }
    report = json.loads(args.output.read_text(encoding="utf-8")) if args.output.exists() else {}
    report.setdefault("schema", "person-search-stack-memory/v1")
    report.setdefault(
        "method",
        {
            "containers": "docker stats --no-stream MemUsage",
            "processes": "psutil RSS (working set on Windows), process plus all children",
            "aggregate": "maximum over samples within a state",
        },
    )
    report.setdefault("states", {})[args.state] = state
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    mib = 2**20
    total = memory.total / mib
    print(f"[{args.state}] machine used max {peak_used / mib:,.0f} MiB of {total:,.0f} MiB")
    for name, value in state["containers_bytes"].items():
        print(f"  {name:40s} {value / mib:8.0f} MiB")
    for group, value in peak_groups.items():
        print(f"  {group:40s} {value['rss_bytes'] / mib:8.0f} MiB ({value['processes']} proc)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
