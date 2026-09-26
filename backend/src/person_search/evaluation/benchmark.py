from __future__ import annotations

import io
import statistics
import sys
import threading
import time
from collections.abc import Callable, Iterable, Iterator, Sequence
from dataclasses import asdict, dataclass, field
from typing import Any

from person_search.evaluation.environment import run_command

REPORT_SCHEMA = "person-search-sampling-benchmark/v1"
DEFAULT_SHORT_TRACK_MS = 2000


def _rusage() -> tuple[float, float, int | None, int | None]:
    try:
        import resource
    except ImportError:
        return time.process_time(), 0.0, None, None
    scale = 1 if sys.platform == "darwin" else 1024
    own = resource.getrusage(resource.RUSAGE_SELF)
    children = resource.getrusage(resource.RUSAGE_CHILDREN)
    return (
        own.ru_utime + own.ru_stime,
        children.ru_utime + children.ru_stime,
        int(own.ru_maxrss * scale),
        int(children.ru_maxrss * scale),
    )


class GpuMemorySampler:
    def __init__(
        self,
        *,
        interval: float = 0.5,
        runner: Callable[[list[str]], str | None] = run_command,
    ) -> None:
        self.interval = interval
        self.runner = runner
        self.peak_mib: float | None = None
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def _sample(self) -> None:
        output = self.runner(
            ["nvidia-smi", "--query-gpu=memory.used", "--format=csv,noheader,nounits"]
        )
        if not output:
            return
        try:
            used = max(float(line.strip()) for line in output.splitlines() if line.strip())
        except ValueError:
            return
        self.peak_mib = used if self.peak_mib is None else max(self.peak_mib, used)

    def _loop(self) -> None:
        while not self._stop.wait(self.interval):
            self._sample()

    def __enter__(self) -> GpuMemorySampler:
        self._sample()
        if self.peak_mib is not None:
            self._thread = threading.Thread(target=self._loop, daemon=True)
            self._thread.start()
        return self

    def __exit__(self, *args: object) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=5)
        self._sample()


class LimitedSource:
    def __init__(self, source: Any, limit: int | None) -> None:
        self.source = source
        self.limit = limit

    def __enter__(self) -> LimitedSource:
        self.source.__enter__()
        return self

    def __exit__(self, *args: object) -> None:
        self.source.__exit__(*args)

    def __iter__(self) -> Iterator[Any]:
        for index, frame in enumerate(self.source):
            if self.limit is not None and index >= self.limit:
                frame.image.close()
                return
            yield frame


@dataclass
class RunMeasurement:
    video: str
    sampling_interval: int
    repeat: int
    cold: bool
    wall_seconds: float
    source_frames: int
    sampled_frames: int
    source_fps: float
    sampled_fps: float
    tracks: int
    short_tracks: int
    stage_mean_ms: dict[str, float]
    stage_total_ms: dict[str, float]
    cpu_seconds_self: float
    cpu_seconds_children: float
    peak_rss_bytes_self: int | None
    peak_rss_bytes_children: int | None
    peak_gpu_memory_mib: float | None
    representative_jpeg_bytes: int
    error: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)


def _jpeg_size(image: Any) -> int:
    buffer = io.BytesIO()
    image.save(buffer, format="JPEG", quality=90)
    return buffer.tell()


def measure_run(
    *,
    video: str,
    sampling_interval: int,
    repeat: int,
    cold: bool,
    pipeline_factory: Callable[[int], Any],
    source_factory: Callable[[], Any],
    clock: Callable[[], float] = time.perf_counter,
    usage: Callable[[], tuple[float, float, int | None, int | None]] = _rusage,
    gpu: Callable[[], Any] = GpuMemorySampler,
    short_track_ms: int = DEFAULT_SHORT_TRACK_MS,
) -> RunMeasurement:
    cpu_self_before, cpu_children_before, _, _ = usage()
    started = clock()
    result = None
    error = None
    with gpu() as sampler:
        try:
            pipeline = pipeline_factory(sampling_interval)
            with source_factory() as source:
                result = pipeline.run(source)
        except Exception as exc:
            error = type(exc).__name__
    wall = max(clock() - started, 1e-9)
    cpu_self_after, cpu_children_after, peak_self, peak_children = usage()
    tracks = short = jpeg_bytes = 0
    stage_mean: dict[str, float] = {}
    stage_total: dict[str, float] = {}
    source_frames = sampled_frames = 0
    if result is not None:
        source_frames, sampled_frames = result.source_frames, result.sampled_frames
        tracks = len(result.encoded_tracks)
        images = {}
        for item in result.encoded_tracks:
            track = item.track
            if track.source_ended_at_ms - track.source_started_at_ms < short_track_ms:
                short += 1
            images[id(track.representative.frame.image)] = track.representative.frame.image
        try:
            jpeg_bytes = sum(_jpeg_size(image) for image in images.values())
        finally:
            for image in images.values():
                image.close()
        for timing in result.timings:
            stage_total[timing.stage] = round(timing.elapsed_ms, 3)
            stage_mean[timing.stage] = (
                round(timing.elapsed_ms / timing.calls, 3) if timing.calls else 0.0
            )
    return RunMeasurement(
        video=video,
        sampling_interval=sampling_interval,
        repeat=repeat,
        cold=cold,
        wall_seconds=round(wall, 3),
        source_frames=source_frames,
        sampled_frames=sampled_frames,
        source_fps=round(source_frames / wall, 3),
        sampled_fps=round(sampled_frames / wall, 3),
        tracks=tracks,
        short_tracks=short,
        stage_mean_ms=stage_mean,
        stage_total_ms=stage_total,
        cpu_seconds_self=round(cpu_self_after - cpu_self_before, 3),
        cpu_seconds_children=round(cpu_children_after - cpu_children_before, 3),
        peak_rss_bytes_self=peak_self,
        peak_rss_bytes_children=peak_children,
        peak_gpu_memory_mib=sampler.peak_mib,
        representative_jpeg_bytes=jpeg_bytes,
        error=error,
    )


def run_benchmark(
    videos: Sequence[str],
    intervals: Sequence[int],
    repeats: int,
    measure: Callable[..., RunMeasurement],
) -> list[RunMeasurement]:
    if repeats < 1 or not intervals or not videos:
        raise ValueError("Benchmark needs videos, intervals and at least one repeat.")
    measurements = []
    first = True
    for video in videos:
        for repeat in range(1, repeats + 1):
            for interval in intervals:
                measurements.append(
                    measure(video=video, sampling_interval=interval, repeat=repeat, cold=first)
                )
                first = False
    return measurements


def _stats(values: Iterable[float]) -> dict[str, float] | None:
    items = sorted(values)
    if not items:
        return None
    index = max(0, min(len(items) - 1, round(0.95 * (len(items) - 1))))
    return {
        "mean": round(statistics.fmean(items), 3),
        "median": round(statistics.median(items), 3),
        "p95": round(items[index], 3),
        "min": round(items[0], 3),
        "max": round(items[-1], 3),
        "n": len(items),
    }


def summarize(measurements: Sequence[RunMeasurement]) -> dict[str, Any]:
    by_interval: dict[int, list[RunMeasurement]] = {}
    for item in measurements:
        by_interval.setdefault(item.sampling_interval, []).append(item)
    summary: dict[str, Any] = {}
    for interval, items in sorted(by_interval.items()):
        ok = [item for item in items if item.error is None]
        warm = [item for item in ok if not item.cold]
        stages = sorted({stage for item in ok for stage in item.stage_mean_ms})
        peaks_self = [item.peak_rss_bytes_self for item in ok if item.peak_rss_bytes_self]
        peaks_children = [
            item.peak_rss_bytes_children for item in ok if item.peak_rss_bytes_children
        ]
        gpu = [item.peak_gpu_memory_mib for item in ok if item.peak_gpu_memory_mib is not None]
        summary[f"N={interval}"] = {
            "runs": len(items),
            "failed_runs": len(items) - len(ok),
            "errors": sorted({item.error for item in items if item.error}),
            "cold_wall_seconds": _stats(item.wall_seconds for item in ok if item.cold),
            "warm_wall_seconds": _stats(item.wall_seconds for item in warm),
            "source_fps": _stats(item.source_fps for item in warm or ok),
            "sampled_fps": _stats(item.sampled_fps for item in warm or ok),
            "tracks": _stats(item.tracks for item in ok),
            "short_tracks": _stats(item.short_tracks for item in ok),
            "stage_mean_ms": {
                stage: _stats(
                    item.stage_mean_ms[stage] for item in warm or ok if stage in item.stage_mean_ms
                )
                for stage in stages
            },
            "peak_rss_bytes_self": max(peaks_self) if peaks_self else None,
            "peak_rss_bytes_children": max(peaks_children) if peaks_children else None,
            "peak_gpu_memory_mib": max(gpu) if gpu else None,
            "representative_jpeg_bytes": _stats(item.representative_jpeg_bytes for item in ok),
        }
    baseline = summary.get("N=10")
    comparisons = {}
    for key, row in summary.items():
        if key == "N=10" or baseline is None:
            continue
        comparisons[f"{key} vs N=10"] = {
            metric: _ratio(row, baseline, metric)
            for metric in ("warm_wall_seconds", "sampled_fps", "tracks", "short_tracks")
        }
    return {"by_interval": summary, "comparisons": comparisons}


def _ratio(row: dict[str, Any], baseline: dict[str, Any], metric: str) -> float | None:
    left, right = row.get(metric), baseline.get(metric)
    if not left or not right or not right.get("median"):
        return None
    return round(left["median"] / right["median"], 4)


def measurements_as_dicts(measurements: Sequence[RunMeasurement]) -> list[dict[str, Any]]:
    return [asdict(item) for item in measurements]
