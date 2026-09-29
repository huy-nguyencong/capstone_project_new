from __future__ import annotations

import json
import uuid
from types import SimpleNamespace

import pytest
from PIL import Image

from person_search.evaluation.benchmark import (
    GpuMemorySampler,
    LimitedSource,
    ProcessTreeSampler,
    measure_run,
    measurements_as_dicts,
    run_benchmark,
    summarize,
)
from person_search.workers.contracts import SourceFrame
from person_search.workers.production import ProductionPipelineResult, StageTiming

pytestmark = pytest.mark.unit


class Clock:
    def __init__(self, step):
        self.value = 0.0
        self.step = step

    def __call__(self):
        self.value += self.step
        return self.value


def usage_sequence(*values):
    items = iter(values)
    return lambda: next(items)


class NoGpu:
    peak_mib = None

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return None


def encoded(started, ended, image):
    frame = SimpleNamespace(image=image)
    track = SimpleNamespace(
        source_started_at_ms=started,
        source_ended_at_ms=ended,
        representative=SimpleNamespace(frame=frame),
    )
    return SimpleNamespace(track=track)


class Pipeline:
    def __init__(self, interval, images, *, error=None):
        self.interval = interval
        self.images = images
        self.error = error

    def run(self, source):
        frames = list(source)
        for frame in frames:
            frame.image.close()
        if self.error is not None:
            raise self.error
        shared = self.images[0]
        return ProductionPipelineResult(
            len(frames),
            len(frames) // self.interval,
            4,
            6,
            (
                encoded(0, 5000, shared),
                encoded(1000, 1500, shared),
                encoded(0, 900, self.images[1]),
            ),
            (StageTiming("detector", 4, 80.0), StageTiming("load", 1, 500.0)),
        )


class Source:
    def __init__(self, count):
        self.count = count
        self.images = []
        self.closed = False

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.closed = True

    def __iter__(self):
        camera = uuid.uuid4()
        for index in range(self.count):
            image = Image.new("RGB", (8, 8))
            self.images.append(image)
            yield SourceFrame(camera, index, index * 40, image, 8, 8)


def is_closed(image):
    try:
        image.getpixel((0, 0))
    except ValueError:
        return True
    return False


def test_measure_run_reports_rates_stages_resources_and_closes_images():
    images = [Image.new("RGB", (32, 64), "red"), Image.new("RGB", (32, 64), "blue")]
    source = Source(40)

    measurement = measure_run(
        video="cam1.mp4",
        sampling_interval=10,
        repeat=1,
        cold=True,
        pipeline_factory=lambda interval: Pipeline(interval, images),
        source_factory=lambda: LimitedSource(source, 20),
        clock=Clock(2.0),
        usage=usage_sequence((1.0, 2.0, 100, 200), (3.5, 10.0, 300, 900)),
        gpu=NoGpu,
    )

    assert measurement.source_frames == 20 and measurement.sampled_frames == 2
    assert measurement.wall_seconds == 2.0
    assert measurement.source_fps == 10.0 and measurement.sampled_fps == 1.0
    assert measurement.tracks == 3 and measurement.short_tracks == 2
    assert measurement.stage_mean_ms == {"detector": 20.0, "load": 500.0}
    assert measurement.cpu_seconds_self == 2.5 and measurement.cpu_seconds_children == 8.0
    assert (measurement.peak_rss_bytes_self, measurement.peak_rss_bytes_children) == (300, 900)
    assert measurement.representative_jpeg_bytes > 0
    assert all(is_closed(image) for image in images)
    assert all(is_closed(image) for image in source.images)
    assert source.closed
    json.dumps(measurements_as_dicts([measurement]))


def test_measure_run_records_failure_without_raising():
    measurement = measure_run(
        video="cam1.mp4",
        sampling_interval=20,
        repeat=1,
        cold=False,
        pipeline_factory=lambda interval: Pipeline(interval, [], error=MemoryError()),
        source_factory=lambda: Source(3),
        clock=Clock(1.0),
        usage=usage_sequence((0.0, 0.0, None, None), (0.0, 0.0, None, None)),
        gpu=NoGpu,
    )
    assert measurement.error == "MemoryError"
    assert measurement.tracks == 0 and measurement.source_fps == 0.0


def test_run_benchmark_interleaves_intervals_and_marks_only_first_run_cold():
    calls = []

    def measure(**kwargs):
        calls.append(kwargs)
        return SimpleNamespace(**kwargs)

    run_benchmark(["a.mp4", "b.mp4"], [10, 20], 2, measure)

    assert [(c["video"], c["repeat"], c["sampling_interval"]) for c in calls] == [
        ("a.mp4", 1, 10),
        ("a.mp4", 1, 20),
        ("a.mp4", 2, 10),
        ("a.mp4", 2, 20),
        ("b.mp4", 1, 10),
        ("b.mp4", 1, 20),
        ("b.mp4", 2, 10),
        ("b.mp4", 2, 20),
    ]
    assert [c["cold"] for c in calls] == [True] + [False] * 7
    with pytest.raises(ValueError):
        run_benchmark([], [10], 1, measure)


def fake_measurement(interval, repeat, cold, wall, tracks, *, error=None, gpu=None):
    return SimpleNamespace(
        sampling_interval=interval,
        repeat=repeat,
        cold=cold,
        wall_seconds=wall,
        source_fps=1000 / wall,
        sampled_fps=1000 / wall / interval,
        tracks=tracks,
        short_tracks=tracks // 4,
        stage_mean_ms={"detector": 50.0 + interval},
        peak_rss_bytes_self=1000,
        peak_rss_bytes_children=5000 + interval,
        peak_gpu_memory_mib=gpu,
        representative_jpeg_bytes=tracks * 100,
        error=error,
    )


def test_summarize_separates_cold_warm_and_compares_against_n10():
    measurements = [
        fake_measurement(10, 1, True, 100.0, 40),
        fake_measurement(20, 1, False, 50.0, 48),
        fake_measurement(10, 2, False, 80.0, 40),
        fake_measurement(20, 2, False, 40.0, 52, gpu=2048.0),
        fake_measurement(20, 3, False, 0.1, 0, error="MemoryError"),
    ]

    summary = summarize(measurements)
    n10, n20 = summary["by_interval"]["N=10"], summary["by_interval"]["N=20"]

    assert n10["cold_wall_seconds"]["median"] == 100.0
    assert n10["warm_wall_seconds"]["median"] == 80.0
    assert n20["cold_wall_seconds"] is None
    assert n20["warm_wall_seconds"]["median"] == 45.0
    assert n20["failed_runs"] == 1 and n20["errors"] == ["MemoryError"]
    assert n20["peak_gpu_memory_mib"] == 2048.0 and n10["peak_gpu_memory_mib"] is None
    assert n20["stage_mean_ms"]["detector"]["median"] == 70.0
    comparison = summary["comparisons"]["N=20 vs N=10"]
    assert comparison["warm_wall_seconds"] == pytest.approx(45.0 / 80.0, abs=1e-4)
    assert comparison["tracks"] == pytest.approx(50.0 / 40.0, abs=1e-4)


def test_gpu_sampler_tracks_peak_and_is_silent_without_nvidia_smi():
    readings = iter(["1000", "3000\n1500", "2000"])
    with GpuMemorySampler(interval=10, runner=lambda command: next(readings, None)) as sampler:
        pass
    assert sampler.peak_mib == 3000.0

    with GpuMemorySampler(runner=lambda command: None) as empty:
        pass
    assert empty.peak_mib is None


def test_limited_source_closes_frames_beyond_the_limit():
    source = Source(5)
    with LimitedSource(source, 2) as limited:
        frames = list(limited)
    assert len(frames) == 2
    assert is_closed(source.images[2])
    assert source.closed


class FakeProcess:
    """psutil.Process stand-in: RSS/CPU values advance on each read."""

    def __init__(self, pid, rss, cpu, children=()):
        self.pid = pid
        self.rss = list(rss)
        self.cpu = list(cpu)
        self._children = list(children)

    def memory_info(self):
        value = self.rss.pop(0) if len(self.rss) > 1 else self.rss[0]
        return SimpleNamespace(rss=value)

    def cpu_times(self):
        value = self.cpu.pop(0) if len(self.cpu) > 1 else self.cpu[0]
        return SimpleNamespace(user=value, system=0.0)

    def create_time(self):
        return 1.0

    def children(self, recursive=False):
        return self._children


def test_process_tree_sampler_includes_model_children():
    child = FakeProcess(2, rss=[400, 700], cpu=[0.0, 6.0])
    parent = FakeProcess(1, rss=[100, 250], cpu=[1.0, 4.0], children=[child])
    sampler = ProcessTreeSampler(interval=60, process=parent)
    assert sampler.available

    with sampler:
        pass

    assert (sampler.peak_self, sampler.peak_children) == (250, 700)
    assert sampler.cpu_self == 3.0 and sampler.cpu_children == 6.0


def test_measure_run_uses_process_tree_figures_when_available():
    class Tree:
        available = True
        interval = 0.25
        cpu_self, cpu_children, peak_self, peak_children = 1.5, 9.0, 111, 999

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return None

    measurement = measure_run(
        video="cam1.mp4",
        sampling_interval=20,
        repeat=1,
        cold=False,
        pipeline_factory=lambda interval: Pipeline(interval, []),
        source_factory=lambda: Source(3),
        clock=Clock(1.0),
        usage=usage_sequence((0.0, 0.0, None, None), (0.0, 0.0, None, None)),
        gpu=NoGpu,
        processes=Tree,
    )

    assert (measurement.cpu_seconds_self, measurement.cpu_seconds_children) == (1.5, 9.0)
    assert (measurement.peak_rss_bytes_self, measurement.peak_rss_bytes_children) == (111, 999)
    assert measurement.extra["resource_method"].startswith("psutil")
