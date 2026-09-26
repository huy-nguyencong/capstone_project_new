"""Runtime, device, codec, artifact, and resource preflight for AI workers."""

from __future__ import annotations

import ctypes
import hashlib
import importlib.metadata
import json
import os
import platform
import shutil
import subprocess
import sys
from collections.abc import Callable, Mapping
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any, Protocol

import av

from person_search.ai.registry import (
    DeviceKind,
    ModelRegistry,
    RegistryEntryBase,
    RegistryMode,
)

MIB = 1024 * 1024


class PreflightConfigurationError(ValueError):
    pass


class PreflightFailedError(RuntimeError):
    """Safe startup failure raised before a worker can claim a job."""

    def __init__(self, failure_codes: tuple[str, ...]) -> None:
        super().__init__("AI worker preflight failed: " + ", ".join(failure_codes))
        self.failure_codes = failure_codes


class CheckOutcome(StrEnum):
    PASS = "PASS"
    WARN = "WARN"
    FAIL = "FAIL"


class DevicePreference(StrEnum):
    CPU = "cpu"
    CUDA = "cuda"
    AUTO = "auto"


@dataclass(frozen=True, slots=True)
class ResourceSettings:
    profile: str
    device_preference: DevicePreference
    require_cuda: bool
    min_free_ram_mb: int
    min_free_disk_mb: int
    worker_threads: int
    decode_threads: int
    inference_timeout_seconds: int
    source_timeout_seconds: int
    batch_size: int
    frame_queue_capacity: int
    max_active_tracks: int
    max_track_candidates: int
    max_frame_pixels: int

    def __post_init__(self) -> None:
        if not isinstance(self.device_preference, DevicePreference):
            raise PreflightConfigurationError("device_preference is invalid.")
        if type(self.require_cuda) is not bool:
            raise PreflightConfigurationError("require_cuda must be boolean.")
        positive = {
            "min_free_ram_mb": self.min_free_ram_mb,
            "min_free_disk_mb": self.min_free_disk_mb,
            "worker_threads": self.worker_threads,
            "decode_threads": self.decode_threads,
            "inference_timeout_seconds": self.inference_timeout_seconds,
            "source_timeout_seconds": self.source_timeout_seconds,
            "batch_size": self.batch_size,
            "frame_queue_capacity": self.frame_queue_capacity,
            "max_active_tracks": self.max_active_tracks,
            "max_track_candidates": self.max_track_candidates,
            "max_frame_pixels": self.max_frame_pixels,
        }
        for name, value in positive.items():
            if isinstance(value, bool) or not isinstance(value, int) or value < 1:
                raise PreflightConfigurationError(f"{name} must be a positive integer.")
        if self.require_cuda and self.device_preference is not DevicePreference.CUDA:
            raise PreflightConfigurationError("require_cuda requires device_preference=cuda.")
        if not 1 <= self.worker_threads <= 8 or not 1 <= self.decode_threads <= 4:
            raise PreflightConfigurationError("Thread limits exceed the supported safe range.")
        if self.batch_size != 1:
            raise PreflightConfigurationError("batch_size must remain 1 until AIW-27 benchmark.")
        if self.max_track_candidates > 3:
            raise PreflightConfigurationError("max_track_candidates must not exceed 3.")
        if self.frame_queue_capacity > 32 or self.max_active_tracks > 4096:
            raise PreflightConfigurationError("Buffer limits exceed the supported safe range.")


@dataclass(frozen=True, slots=True)
class MemorySnapshot:
    total_bytes: int
    available_bytes: int


@dataclass(frozen=True, slots=True)
class DiskSnapshot:
    total_bytes: int
    free_bytes: int


@dataclass(frozen=True, slots=True)
class TorchSnapshot:
    installed_version: str | None
    import_ok: bool
    cuda_version: str | None
    cuda_available: bool
    gpu_names: tuple[str, ...]
    error_code: str | None = None


@dataclass(frozen=True, slots=True)
class CodecSnapshot:
    pyav_version: str
    codecs: tuple[str, ...]
    ffmpeg_version: str | None
    ffprobe_version: str | None
    ready: bool


@dataclass(frozen=True, slots=True)
class HardwareSnapshot:
    cpu_count: int
    machine: str
    display_adapters: tuple[str, ...]
    igpu_detected: bool


@dataclass(frozen=True, slots=True)
class PreflightCheck:
    component: str
    outcome: CheckOutcome
    code: str
    message: str
    details: Mapping[str, Any]


@dataclass(frozen=True, slots=True)
class ModelMemoryMeasurement:
    model_id: str
    before_bytes: int
    after_bytes: int
    delta_bytes: int


@dataclass(frozen=True, slots=True)
class ModelPreflightResult:
    model_id: str
    version: str
    adapter_kind: str
    artifact_sha256: str
    outcome: CheckOutcome
    code: str
    device: str | None
    blockers: tuple[str, ...]
    memory: ModelMemoryMeasurement | None


@dataclass(frozen=True, slots=True)
class PreflightReport:
    schema_version: str
    generated_at: datetime
    ready: bool
    profile: ResourceSettings
    selected_device: str | None
    python_version: str
    platform: str
    memory: MemorySnapshot
    disk: DiskSnapshot
    torch: TorchSnapshot
    codecs: CodecSnapshot
    hardware: HardwareSnapshot
    process_idle_bytes: int
    nvidia_smi: tuple[str, ...]
    packages: Mapping[str, str]
    package_lock_sha256: str
    registry_schema_version: str
    registry_mode: str
    model_results: tuple[ModelPreflightResult, ...]
    preflight_available_ids: tuple[str, ...]
    checks: tuple[PreflightCheck, ...]

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["generated_at"] = self.generated_at.isoformat().replace("+00:00", "Z")
        payload["profile"]["device_preference"] = self.profile.device_preference.value
        return payload


class ModelLoadProbe(Protocol):
    def __call__(self, entry: RegistryEntryBase, device: str) -> object | None: ...


@dataclass(frozen=True, slots=True)
class PreflightProbes:
    memory: Callable[[], MemorySnapshot]
    disk: Callable[[Path], DiskSnapshot]
    torch: Callable[[], TorchSnapshot]
    codecs: Callable[[], CodecSnapshot]
    hardware: Callable[[], HardwareSnapshot]
    process_memory: Callable[[], int]
    packages: Callable[[], Mapping[str, str]]
    nvidia_smi: Callable[[], tuple[str, ...]]


def _exact_keys(value: Mapping[str, Any], expected: set[str], location: str) -> None:
    unknown, missing = set(value) - expected, expected - set(value)
    if unknown or missing:
        raise PreflightConfigurationError(
            f"{location} fields mismatch; missing={sorted(missing)}, unknown={sorted(unknown)}."
        )


def load_resource_settings(path: str | Path, profile: str) -> ResourceSettings:
    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise PreflightConfigurationError("Resource profile file is not valid UTF-8 JSON.") from exc
    if not isinstance(payload, dict):
        raise PreflightConfigurationError("Resource profile root must be an object.")
    _exact_keys(payload, {"schema_version", "profiles"}, "root")
    if payload["schema_version"] != "ai-resource-profiles/v1":
        raise PreflightConfigurationError("Unsupported resource profile schema_version.")
    profiles = payload["profiles"]
    if not isinstance(profiles, dict) or profile not in profiles:
        raise PreflightConfigurationError(f"Unknown resource profile: {profile}.")
    data = profiles[profile]
    if not isinstance(data, dict):
        raise PreflightConfigurationError(f"Profile {profile} must be an object.")
    fields = {
        "device_preference",
        "require_cuda",
        "min_free_ram_mb",
        "min_free_disk_mb",
        "worker_threads",
        "decode_threads",
        "inference_timeout_seconds",
        "source_timeout_seconds",
        "batch_size",
        "frame_queue_capacity",
        "max_active_tracks",
        "max_track_candidates",
        "max_frame_pixels",
    }
    _exact_keys(data, fields, f"profiles.{profile}")
    try:
        preference = DevicePreference(data["device_preference"])
    except (TypeError, ValueError):
        raise PreflightConfigurationError("device_preference must be cpu, cuda, or auto.") from None
    return ResourceSettings(profile=profile, device_preference=preference, **{
        key: value for key, value in data.items() if key != "device_preference"
    })


def apply_resource_environment(settings: ResourceSettings) -> None:
    """Apply bounded thread settings before importing model frameworks."""

    values = {
        "OMP_NUM_THREADS": settings.worker_threads,
        "MKL_NUM_THREADS": settings.worker_threads,
        "OPENBLAS_NUM_THREADS": settings.worker_threads,
        "NUMEXPR_NUM_THREADS": settings.worker_threads,
        "TOKENIZERS_PARALLELISM": "false",
    }
    for name, value in values.items():
        os.environ[name] = str(value)


def _memory_snapshot() -> MemorySnapshot:
    if os.name == "nt":
        class MemoryStatus(ctypes.Structure):
            _fields_ = [
                ("length", ctypes.c_ulong),
                ("memory_load", ctypes.c_ulong),
                ("total_physical", ctypes.c_ulonglong),
                ("available_physical", ctypes.c_ulonglong),
                ("total_page_file", ctypes.c_ulonglong),
                ("available_page_file", ctypes.c_ulonglong),
                ("total_virtual", ctypes.c_ulonglong),
                ("available_virtual", ctypes.c_ulonglong),
                ("available_extended_virtual", ctypes.c_ulonglong),
            ]

        status = MemoryStatus()
        status.length = ctypes.sizeof(status)
        if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
            raise OSError("GlobalMemoryStatusEx failed")
        return MemorySnapshot(status.total_physical, status.available_physical)
    page_size = os.sysconf("SC_PAGE_SIZE")
    total = page_size * os.sysconf("SC_PHYS_PAGES")
    available = page_size * os.sysconf("SC_AVPHYS_PAGES")
    return MemorySnapshot(total, available)


def _disk_snapshot(path: Path) -> DiskSnapshot:
    usage = shutil.disk_usage(path)
    return DiskSnapshot(usage.total, usage.free)


def _run_version(binary: str) -> str | None:
    try:
        result = subprocess.run(
            [binary, "-version"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return None
    first_line = (result.stdout or result.stderr).splitlines()
    return first_line[0][:300] if result.returncode == 0 and first_line else None


def _codec_snapshot() -> CodecSnapshot:
    codecs = []
    for name in ("h264", "mpeg4"):
        try:
            av.codec.Codec(name, "r")
            codecs.append(name)
        except (ValueError, av.error.FFmpegError):
            continue
    ffmpeg, ffprobe = _run_version("ffmpeg"), _run_version("ffprobe")
    return CodecSnapshot(
        pyav_version=av.__version__,
        codecs=tuple(codecs),
        ffmpeg_version=ffmpeg,
        ffprobe_version=ffprobe,
        ready={"h264", "mpeg4"}.issubset(codecs) and bool(ffmpeg and ffprobe),
    )


def _torch_snapshot() -> TorchSnapshot:
    try:
        installed = importlib.metadata.version("torch")
    except importlib.metadata.PackageNotFoundError:
        return TorchSnapshot(None, False, None, False, (), "torch_not_installed")
    script = (
        "import json,torch; "
        "print(json.dumps({'version':torch.__version__,'cuda_version':torch.version.cuda,"
        "'cuda_available':torch.cuda.is_available(),'gpus':[torch.cuda.get_device_name(i) "
        "for i in range(torch.cuda.device_count())]}))"
    )
    try:
        result = subprocess.run(
            [sys.executable, "-c", script],
            capture_output=True,
            text=True,
            timeout=20,
            check=False,
        )
        if result.returncode:
            return TorchSnapshot(installed, False, None, False, (), "torch_import_failed")
        payload = json.loads(result.stdout)
        return TorchSnapshot(
            installed,
            True,
            payload.get("cuda_version"),
            payload.get("cuda_available") is True,
            tuple(str(name)[:200] for name in payload.get("gpus", [])),
        )
    except (OSError, subprocess.TimeoutExpired, json.JSONDecodeError, TypeError):
        return TorchSnapshot(installed, False, None, False, (), "torch_probe_failed")


def _display_adapters() -> tuple[str, ...]:
    commands = []
    if os.name == "nt":
        commands.append(
            [
                "powershell",
                "-NoProfile",
                "-Command",
                "Get-CimInstance Win32_VideoController | Select-Object -ExpandProperty Name",
            ]
        )
    elif shutil.which("lspci"):
        commands.append(["lspci"])
    for command in commands:
        try:
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=5,
                check=False,
            )
        except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
            continue
        if result.returncode == 0:
            lines = []
            for line in result.stdout.splitlines():
                if os.name == "nt" or "vga" in line.lower() or "3d controller" in line.lower():
                    lines.append(line.strip()[:300])
            return tuple(lines)
    return ()


def _hardware_snapshot() -> HardwareSnapshot:
    adapters = _display_adapters()
    igpu = any(
        marker in adapter.lower()
        for adapter in adapters
        for marker in ("intel", "radeon graphics", "integrated")
    )
    return HardwareSnapshot(os.cpu_count() or 1, platform.machine(), adapters, igpu)


def _process_memory_bytes() -> int:
    if os.name == "nt":
        from ctypes import wintypes

        class Counters(ctypes.Structure):
            _fields_ = [
                ("cb", wintypes.DWORD),
                ("page_fault_count", wintypes.DWORD),
                ("peak_working_set_size", ctypes.c_size_t),
                ("working_set_size", ctypes.c_size_t),
                ("quota_peak_paged_pool_usage", ctypes.c_size_t),
                ("quota_paged_pool_usage", ctypes.c_size_t),
                ("quota_peak_non_paged_pool_usage", ctypes.c_size_t),
                ("quota_non_paged_pool_usage", ctypes.c_size_t),
                ("pagefile_usage", ctypes.c_size_t),
                ("peak_pagefile_usage", ctypes.c_size_t),
            ]

        counters = Counters()
        counters.cb = ctypes.sizeof(counters)
        get_process = ctypes.windll.kernel32.GetCurrentProcess
        get_process.restype = wintypes.HANDLE
        get_memory = ctypes.windll.psapi.GetProcessMemoryInfo
        get_memory.argtypes = [wintypes.HANDLE, ctypes.POINTER(Counters), wintypes.DWORD]
        get_memory.restype = wintypes.BOOL
        if not get_memory(get_process(), ctypes.byref(counters), counters.cb):
            raise OSError("GetProcessMemoryInfo failed")
        return int(counters.working_set_size)
    statm = Path("/proc/self/statm")
    if statm.is_file():
        resident_pages = int(statm.read_text(encoding="ascii").split()[1])
        return resident_pages * os.sysconf("SC_PAGE_SIZE")
    import resource

    value = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return int(value if sys.platform == "darwin" else value * 1024)


def _package_versions() -> Mapping[str, str]:
    result = {}
    for distribution in importlib.metadata.distributions():
        name = distribution.metadata.get("Name")
        if name:
            result[name.lower()] = distribution.version
    return dict(sorted(result.items()))


def _nvidia_smi() -> tuple[str, ...]:
    try:
        result = subprocess.run(
            [
                "nvidia-smi",
                "--query-gpu=name,driver_version,memory.total",
                "--format=csv,noheader,nounits",
            ],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return ()
    if result.returncode:
        return ()
    return tuple(line.strip()[:300] for line in result.stdout.splitlines() if line.strip())


def default_probes() -> PreflightProbes:
    return PreflightProbes(
        memory=_memory_snapshot,
        disk=_disk_snapshot,
        torch=_torch_snapshot,
        codecs=_codec_snapshot,
        hardware=_hardware_snapshot,
        process_memory=_process_memory_bytes,
        packages=_package_versions,
        nvidia_smi=_nvidia_smi,
    )


_ADAPTER_PACKAGES = {
    "ultralytics_yolo": ("torch", "torchvision", "ultralytics"),
    "yolox": ("torch", "torchvision"),
    "bytetrack": ("ultralytics", "lap"),
    "botsort": (),
    "rasa": ("torch", "torchvision", "transformers", "timm"),
    "demo_detector": (),
    "demo_tracker": (),
    "demo_encoder": (),
}

_RASA_UPSTREAM_BASELINE = {
    "torch": "1.9.1",
    "torchvision": "0.10.1",
    "transformers": "4.8.1",
    "timm": "0.4.9",
}


def _check(
    component: str,
    outcome: CheckOutcome,
    code: str,
    message: str,
    **details: Any,
) -> PreflightCheck:
    return PreflightCheck(component, outcome, code, message, details)


def _selected_device(
    settings: ResourceSettings, torch: TorchSnapshot
) -> tuple[str | None, PreflightCheck]:
    if settings.device_preference is DevicePreference.CUDA:
        if torch.import_ok and torch.cuda_available and torch.gpu_names:
            return "cuda", _check("device", CheckOutcome.PASS, "cuda_ready", "CUDA is ready.")
        return None, _check(
            "device", CheckOutcome.FAIL, "cuda_unavailable", "CUDA is required but unavailable."
        )
    if settings.device_preference is DevicePreference.AUTO and torch.cuda_available:
        return "cuda", _check("device", CheckOutcome.PASS, "cuda_selected", "CUDA selected.")
    if torch.import_ok:
        return "cpu", _check("device", CheckOutcome.PASS, "cpu_ready", "CPU runtime is ready.")
    return None, _check(
        "device", CheckOutcome.FAIL, "torch_unavailable", "PyTorch CPU runtime is unavailable."
    )


def run_preflight(
    settings: ResourceSettings,
    registry: ModelRegistry,
    *,
    workspace: str | Path,
    probes: PreflightProbes | None = None,
    model_loaders: Mapping[str, ModelLoadProbe] | None = None,
    clock: Callable[[], datetime] = lambda: datetime.now(UTC),
) -> PreflightReport:
    probes = probes or default_probes()
    model_loaders = model_loaders or {}
    workspace_path = Path(workspace).resolve()
    memory = probes.memory()
    disk = probes.disk(workspace_path)
    torch = probes.torch()
    codecs = probes.codecs()
    hardware = probes.hardware()
    packages = dict(sorted((str(k).lower(), str(v)) for k, v in probes.packages().items()))
    package_lock = hashlib.sha256(
        json.dumps(packages, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    nvidia_smi = probes.nvidia_smi()
    process_idle_bytes = probes.process_memory()
    checks = []
    checks.append(
        _check(
            "python",
            CheckOutcome.PASS if sys.version_info >= (3, 11) else CheckOutcome.FAIL,
            "python_supported" if sys.version_info >= (3, 11) else "python_unsupported",
            "Python runtime version checked.",
            version=platform.python_version(),
        )
    )
    checks.append(
        _check(
            "memory",
            CheckOutcome.PASS
            if memory.available_bytes >= settings.min_free_ram_mb * MIB
            else CheckOutcome.FAIL,
            "ram_sufficient"
            if memory.available_bytes >= settings.min_free_ram_mb * MIB
            else "ram_below_threshold",
            "Available system RAM checked.",
            available_bytes=memory.available_bytes,
            required_bytes=settings.min_free_ram_mb * MIB,
        )
    )
    checks.append(
        _check(
            "disk",
            CheckOutcome.PASS
            if disk.free_bytes >= settings.min_free_disk_mb * MIB
            else CheckOutcome.FAIL,
            "disk_sufficient"
            if disk.free_bytes >= settings.min_free_disk_mb * MIB
            else "disk_below_threshold",
            "Free workspace disk checked.",
            free_bytes=disk.free_bytes,
            required_bytes=settings.min_free_disk_mb * MIB,
        )
    )
    checks.append(
        _check(
            "codec",
            CheckOutcome.PASS if codecs.ready else CheckOutcome.FAIL,
            "codec_ready" if codecs.ready else "codec_unavailable",
            "H.264/MPEG-4 decode and FFmpeg tools checked.",
            codecs=list(codecs.codecs),
        )
    )
    if registry.encoder and registry.encoder.adapter_kind == "rasa":
        missing = sorted(name for name in _RASA_UPSTREAM_BASELINE if name not in packages)
        drift = {
            name: {"upstream": expected, "installed": packages[name]}
            for name, expected in _RASA_UPSTREAM_BASELINE.items()
            if name in packages and packages[name] != expected
        }
        if missing:
            checks.append(
                _check(
                    "rasa_compatibility",
                    CheckOutcome.FAIL,
                    "rasa_dependencies_missing",
                    "RaSa dependencies are incomplete.",
                    missing=missing,
                    upstream_baseline=_RASA_UPSTREAM_BASELINE,
                )
            )
        else:
            checks.append(
                _check(
                    "rasa_compatibility",
                    CheckOutcome.WARN,
                    "rasa_version_drift_requires_smoke"
                    if drift
                    else "rasa_legacy_stack_requires_smoke",
                    "RaSa requires an actual checkpoint smoke test on this runtime.",
                    version_drift=drift,
                    upstream_baseline=_RASA_UPSTREAM_BASELINE,
                )
            )
    demo = registry.mode is RegistryMode.DEMO
    if (
        demo
        and not torch.import_ok
        and not settings.require_cuda
        and settings.device_preference is not DevicePreference.CUDA
    ):
        selected_device = "cpu"
        device_check = _check(
            "device",
            CheckOutcome.PASS,
            "demo_cpu_ready",
            "Demo adapters do not require PyTorch.",
        )
    else:
        selected_device, device_check = _selected_device(settings, torch)
    checks.append(device_check)
    checks.append(
        _check(
            "igpu",
            CheckOutcome.WARN,
            "igpu_detected_not_enabled" if hardware.igpu_detected else "igpu_not_detected",
            "iGPU is informational; OpenVINO/DirectML is not enabled before baseline benchmark.",
            detected=hardware.igpu_detected,
            adapters=list(hardware.display_adapters),
        )
    )

    results = []
    loaded_models: list[object] = []
    entries = (*registry.detectors, *registry.trackers)
    if registry.encoder:
        entries = (*entries, registry.encoder)
    for entry in entries:
        blockers = [reason for reason in entry.unavailable_reasons if reason != "preflight_pending"]
        required_packages = _ADAPTER_PACKAGES[entry.adapter_kind]
        blockers.extend(
            f"package_missing:{name}" for name in required_packages if name not in packages
        )
        if selected_device is None or DeviceKind(selected_device) not in entry.devices:
            blockers.append("device_unsupported")
        loader = model_loaders.get(entry.id)
        memory_measurement = None
        if not blockers and loader is not None:
            before = probes.process_memory()
            try:
                loaded = loader(entry, selected_device or "cpu")
                if loaded is not None:
                    loaded_models.append(loaded)
            except Exception:
                blockers.append("model_load_failed")
            after = probes.process_memory()
            memory_measurement = ModelMemoryMeasurement(
                entry.id, before, after, max(0, after - before)
            )
        elif not blockers and loader is None:
            blockers.append("model_load_probe_missing")
        results.append(
            ModelPreflightResult(
                model_id=entry.id,
                version=entry.version,
                adapter_kind=entry.adapter_kind,
                artifact_sha256=entry.artifact.sha256,
                outcome=CheckOutcome.FAIL if blockers else CheckOutcome.PASS,
                code="model_blocked" if blockers else "model_ready",
                device=selected_device,
                blockers=tuple(blockers),
                memory=memory_measurement,
            )
        )

    passed = {item.model_id for item in results if item.outcome is CheckOutcome.PASS}
    compatible_pipeline = bool(
        registry.encoder
        and registry.encoder.id in passed
        and any(
            detector.id in passed
            and tracker.id in passed
            and detector.id in tracker.compatible_detectors
            for detector in registry.detectors
            for tracker in registry.trackers
        )
    )
    checks.append(
        _check(
            "models",
            CheckOutcome.PASS if compatible_pipeline else CheckOutcome.FAIL,
            "pipeline_models_ready" if compatible_pipeline else "pipeline_models_unavailable",
            "At least one compatible Detector/Tracker/Encoder pipeline checked.",
            ready_model_ids=sorted(passed),
        )
    )
    ready = all(check.outcome is not CheckOutcome.FAIL for check in checks)
    return PreflightReport(
        schema_version="ai-preflight-report/v1",
        generated_at=clock(),
        ready=ready,
        profile=settings,
        selected_device=selected_device,
        python_version=platform.python_version(),
        platform=f"{platform.system()} {platform.release()} {platform.machine()}",
        memory=memory,
        disk=disk,
        torch=torch,
        codecs=codecs,
        hardware=hardware,
        process_idle_bytes=process_idle_bytes,
        nvidia_smi=nvidia_smi,
        packages=packages,
        package_lock_sha256=package_lock,
        registry_schema_version=registry.schema_version,
        registry_mode=registry.mode.value,
        model_results=tuple(results),
        preflight_available_ids=tuple(sorted(passed)),
        checks=tuple(checks),
    )


def require_ready(report: PreflightReport) -> None:
    if report.ready:
        return
    codes = tuple(
        check.code for check in report.checks if check.outcome is CheckOutcome.FAIL
    )
    raise PreflightFailedError(codes)
