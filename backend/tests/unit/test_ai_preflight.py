"""Runtime/device/resource preflight tests without requiring model frameworks."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from person_search.ai.preflight import (
    CheckOutcome,
    CodecSnapshot,
    DevicePreference,
    DiskSnapshot,
    HardwareSnapshot,
    MemorySnapshot,
    PreflightConfigurationError,
    PreflightFailedError,
    PreflightProbes,
    ResourceSettings,
    TorchSnapshot,
    apply_resource_environment,
    load_resource_settings,
    require_ready,
    run_preflight,
)
from person_search.ai.registry import load_registry

pytestmark = [pytest.mark.unit, pytest.mark.contract]

NOW = datetime(2026, 9, 26, 8, 0, tzinfo=UTC)


def settings(**changes) -> ResourceSettings:
    values = dict(
        profile="test",
        device_preference=DevicePreference.CPU,
        require_cuda=False,
        min_free_ram_mb=1024,
        min_free_disk_mb=1024,
        worker_threads=2,
        decode_threads=1,
        inference_timeout_seconds=120,
        source_timeout_seconds=15,
        batch_size=1,
        frame_queue_capacity=4,
        max_active_tracks=256,
        max_track_candidates=3,
        max_frame_pixels=8294400,
    )
    values.update(changes)
    return ResourceSettings(**values)


def fake_probes(
    *,
    memory: MemorySnapshot | None = None,
    disk: DiskSnapshot | None = None,
    torch: TorchSnapshot | None = None,
    codecs: CodecSnapshot | None = None,
    process_values: list[int] | None = None,
) -> PreflightProbes:
    process_values = process_values or [100 * 1024 * 1024] * 20

    def process_memory() -> int:
        return process_values.pop(0)

    return PreflightProbes(
        memory=lambda: memory or MemorySnapshot(16 * 1024**3, 12 * 1024**3),
        disk=lambda _: disk or DiskSnapshot(100 * 1024**3, 50 * 1024**3),
        torch=lambda: torch
        or TorchSnapshot(None, False, None, False, (), "torch_not_installed"),
        codecs=lambda: codecs
        or CodecSnapshot("16.0.1", ("h264", "mpeg4"), "ffmpeg 7", "ffprobe 7", True),
        hardware=lambda: HardwareSnapshot(
            8, "x86_64", ("Intel Integrated Graphics", "NVIDIA T4"), True
        ),
        process_memory=process_memory,
        packages=lambda: {"person-search-backend": "0.1.0"},
        nvidia_smi=lambda: ("Tesla T4, 550.54.15, 15360",),
    )


def demo_registry():
    path = Path(__file__).parents[2] / "config" / "models.demo.json"
    return load_registry(path, allow_demo=True)


def no_op_loaders(registry):
    entries = (*registry.detectors, *registry.trackers, registry.encoder)
    return {entry.id: lambda *_: object() for entry in entries}


def test_demo_preflight_is_ready_without_torch_and_is_reproducible(tmp_path: Path) -> None:
    registry = demo_registry()
    report = run_preflight(
        settings(),
        registry,
        workspace=tmp_path,
        probes=fake_probes(),
        model_loaders=no_op_loaders(registry),
        clock=lambda: NOW,
    )

    assert report.ready is True
    assert report.selected_device == "cpu"
    assert report.preflight_available_ids == (
        "demo_detector",
        "demo_encoder",
        "demo_tracker",
    )
    assert report.nvidia_smi == ("Tesla T4, 550.54.15, 15360",)
    assert len(report.package_lock_sha256) == 64
    assert report.as_dict()["generated_at"] == "2026-09-26T08:00:00Z"


@pytest.mark.parametrize(
    ("probe_changes", "failure_code"),
    [
        ({"memory": MemorySnapshot(8 * 1024**3, 512 * 1024**2)}, "ram_below_threshold"),
        ({"disk": DiskSnapshot(8 * 1024**3, 512 * 1024**2)}, "disk_below_threshold"),
        (
            {"codecs": CodecSnapshot("16", ("mpeg4",), None, None, False)},
            "codec_unavailable",
        ),
    ],
)
def test_resource_and_codec_thresholds_block_readiness(
    tmp_path: Path, probe_changes: dict, failure_code: str
) -> None:
    registry = demo_registry()
    report = run_preflight(
        settings(),
        registry,
        workspace=tmp_path,
        probes=fake_probes(**probe_changes),
        model_loaders=no_op_loaders(registry),
        clock=lambda: NOW,
    )

    assert report.ready is False
    assert failure_code in {
        check.code for check in report.checks if check.outcome is CheckOutcome.FAIL
    }
    with pytest.raises(PreflightFailedError, match=failure_code):
        require_ready(report)


def test_required_cuda_fails_when_runtime_does_not_support_it(tmp_path: Path) -> None:
    registry = demo_registry()
    report = run_preflight(
        settings(device_preference=DevicePreference.CUDA, require_cuda=True),
        registry,
        workspace=tmp_path,
        probes=fake_probes(
            torch=TorchSnapshot("2.7.0", True, None, False, (), None)
        ),
        model_loaders=no_op_loaders(registry),
        clock=lambda: NOW,
    )

    assert report.selected_device is None
    assert "cuda_unavailable" in {check.code for check in report.checks}
    assert report.ready is False


def test_missing_production_artifacts_and_model_probe_block_pipeline(tmp_path: Path) -> None:
    path = Path(__file__).parents[2] / "config" / "models.example.json"
    registry = load_registry(path)
    report = run_preflight(
        settings(),
        registry,
        workspace=tmp_path,
        probes=fake_probes(torch=TorchSnapshot("2.7.0", True, None, False, (), None)),
        clock=lambda: NOW,
    )

    assert report.ready is False
    assert all("artifact_missing" in result.blockers for result in report.model_results)
    assert report.preflight_available_ids == ()


def test_model_loader_measurements_capture_idle_and_post_load_memory(tmp_path: Path) -> None:
    values = [90 * 1024**2] + [100 * 1024**2, 125 * 1024**2] * 3
    loaded = []

    def loader(entry, device):
        loaded.append((entry.id, device))

    registry = demo_registry()
    entries = (*registry.detectors, *registry.trackers, registry.encoder)
    report = run_preflight(
        settings(),
        registry,
        workspace=tmp_path,
        probes=fake_probes(process_values=values),
        model_loaders={entry.id: loader for entry in entries},
        clock=lambda: NOW,
    )

    assert len(loaded) == 3
    assert report.process_idle_bytes == 90 * 1024**2
    assert all(result.memory.delta_bytes == 25 * 1024**2 for result in report.model_results)


def test_resource_config_rejects_unsafe_limits(tmp_path: Path) -> None:
    source = Path(__file__).parents[2] / "config" / "ai_resources.json"
    payload = json.loads(source.read_text(encoding="utf-8"))
    payload["profiles"]["local_cpu"]["batch_size"] = 2
    target = tmp_path / "resources.json"
    target.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(PreflightConfigurationError, match="batch_size"):
        load_resource_settings(target, "local_cpu")


def test_resource_environment_applies_bounded_threads(monkeypatch) -> None:
    for name in (
        "OMP_NUM_THREADS",
        "MKL_NUM_THREADS",
        "OPENBLAS_NUM_THREADS",
        "NUMEXPR_NUM_THREADS",
        "TOKENIZERS_PARALLELISM",
    ):
        monkeypatch.delenv(name, raising=False)

    apply_resource_environment(settings(worker_threads=3))

    assert __import__("os").environ["OMP_NUM_THREADS"] == "3"
    assert __import__("os").environ["TOKENIZERS_PARALLELISM"] == "false"
