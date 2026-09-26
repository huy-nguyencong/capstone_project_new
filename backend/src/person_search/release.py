from __future__ import annotations

import shutil
from collections.abc import Callable, Mapping
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from sqlalchemy.engine import make_url

DEFAULT_SECRET_MARKERS = ("change-me", "changeme", "password", "minioadmin")
FORBIDDEN_TRACKED = (
    ".env",
    "infra/.env",
    "backend/.env",
)
FORBIDDEN_TRACKED_PREFIXES = ("wildtrack-dataset/", "backend/var/")
MODEL_SUFFIXES = (".pth", ".pt", ".onnx", ".engine", ".safetensors")
MAX_TRACKED_MODEL_BYTES = 50 * 1024**2


@dataclass(frozen=True, slots=True)
class Check:
    name: str
    ok: bool
    severity: str
    detail: str


def _check(name: str, ok: bool, detail: str, severity: str = "error") -> Check:
    return Check(name, ok, severity, detail)


def environment_checks(environment: Mapping[str, str]) -> list[Check]:
    checks = [
        _check(
            "environment_is_production",
            environment.get("PERSON_SEARCH_ENV", "").lower() == "production",
            "PERSON_SEARCH_ENV must be production for the demo deployment.",
        ),
        _check(
            "debug_disabled",
            environment.get("PERSON_SEARCH_DEBUG", "false").lower() in {"0", "false", "no", ""},
            "PERSON_SEARCH_DEBUG must be false.",
        ),
        _check(
            "demo_models_disabled",
            environment.get("PERSON_SEARCH_ALLOW_DEMO_MODELS", "0") != "1",
            "PERSON_SEARCH_ALLOW_DEMO_MODELS must not enable fake adapters.",
        ),
        _check(
            "structured_logs",
            environment.get("PERSON_SEARCH_LOG_FORMAT", "json").lower() == "json",
            "PERSON_SEARCH_LOG_FORMAT should stay json so redaction output is structured.",
            "warning",
        ),
        _check(
            "rtsp_key_configured",
            bool(environment.get("PERSON_SEARCH_RTSP_KEY", "").strip()),
            "PERSON_SEARCH_RTSP_KEY is required to store RTSP credentials.",
            "warning",
        ),
    ]
    secrets = []
    dsn = environment.get("PERSON_SEARCH_POSTGRES_DSN", "")
    try:
        password = make_url(dsn).password if dsn else None
    except Exception:
        password = None
    secrets.append(("PERSON_SEARCH_POSTGRES_DSN", password or ""))
    minio_secret = environment.get("PERSON_SEARCH_MINIO_SECRET_KEY", "")
    secrets.append(("PERSON_SEARCH_MINIO_SECRET_KEY", minio_secret))
    for name, value in secrets:
        weak = not value or len(value) < 12 or any(
            marker in value.lower() for marker in DEFAULT_SECRET_MARKERS
        )
        checks.append(
            _check(
                f"secret_{name.lower()}",
                not weak,
                f"{name} must hold a non-default secret of at least 12 characters.",
            )
        )
    return checks


def registry_checks(
    load: Callable[[], Any], detector_id: str, tracker_id: str
) -> list[Check]:
    try:
        registry = load()
    except Exception as error:
        return [_check("registry_loads", False, f"Registry failed: {type(error).__name__}.")]
    if registry is None:
        return [_check("registry_loads", False, "PERSON_SEARCH_MODEL_REGISTRY is not set.")]
    checks = [
        _check(
            "registry_production_mode",
            getattr(registry.mode, "value", registry.mode) == "production",
            "Registry must be in production mode without demo adapters.",
        )
    ]
    try:
        selection = registry.resolve(detector_id, tracker_id)
    except Exception as error:
        checks.append(
            _check(
                "demo_pair_resolves",
                False,
                f"{detector_id}/{tracker_id} unavailable: {type(error).__name__}.",
            )
        )
        return checks
    checks.append(
        _check(
            "demo_pair_resolves",
            True,
            "Detector, Tracker and Encoder artifacts match registry checksums.",
        )
    )
    for component in (selection.detector, selection.tracker, selection.encoder):
        provenance = component.provenance
        checks.append(
            _check(
                f"license_{component.id}",
                bool(provenance.approved_for_project),
                f"{component.id}: {provenance.license} ({provenance.review_note or 'no note'}).",
            )
        )
    return checks


def git_checks(
    tracked: list[str] | None, size_of: Callable[[str], int | None] = lambda path: None
) -> list[Check]:
    if tracked is None:
        return [_check("git_hygiene", False, "git ls-files is unavailable.", "warning")]

    def oversized_model(path: str) -> bool:
        if not path.endswith(MODEL_SUFFIXES):
            return False
        size = size_of(path)
        return size is None or size > MAX_TRACKED_MODEL_BYTES

    offenders = sorted(
        path
        for path in tracked
        if path in FORBIDDEN_TRACKED
        or path.startswith(FORBIDDEN_TRACKED_PREFIXES)
        or oversized_model(path)
    )
    return [
        _check(
            "git_hygiene",
            not offenders,
            "No secrets, dataset or model checkpoints are tracked."
            if not offenders
            else "Tracked forbidden files: " + ", ".join(offenders[:10]),
        )
    ]


def disk_checks(path: Path, minimum_free_bytes: int) -> list[Check]:
    target = path
    while not target.exists() and target != target.parent:
        target = target.parent
    free = shutil.disk_usage(target).free
    return [
        _check(
            "disk_free",
            free >= minimum_free_bytes,
            f"{free / 1024**3:.1f} GiB free at {target.name or target}; "
            f"need {minimum_free_bytes / 1024**3:.1f} GiB.",
        )
    ]


def summarize(checks: list[Check]) -> dict[str, Any]:
    errors = [check for check in checks if not check.ok and check.severity == "error"]
    warnings = [check for check in checks if not check.ok and check.severity == "warning"]
    return {
        "ready": not errors,
        "errors": len(errors),
        "warnings": len(warnings),
        "checks": [asdict(check) for check in checks],
    }
