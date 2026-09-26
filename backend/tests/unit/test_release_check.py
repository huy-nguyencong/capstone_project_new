from __future__ import annotations

from types import SimpleNamespace

import pytest

from person_search.release import (
    MAX_TRACKED_MODEL_BYTES,
    disk_checks,
    environment_checks,
    git_checks,
    registry_checks,
    summarize,
)

pytestmark = pytest.mark.unit

STRONG = "Zq7-rT2m-9vKx-Lp4w"
PRODUCTION = {
    "PERSON_SEARCH_ENV": "production",
    "PERSON_SEARCH_DEBUG": "false",
    "PERSON_SEARCH_ALLOW_DEMO_MODELS": "0",
    "PERSON_SEARCH_LOG_FORMAT": "json",
    "PERSON_SEARCH_RTSP_KEY": "fernet-key",
    "PERSON_SEARCH_POSTGRES_DSN": f"postgresql+psycopg://app:{STRONG}@db:5432/app",
    "PERSON_SEARCH_MINIO_SECRET_KEY": STRONG,
}


def by_name(checks):
    return {check.name: check for check in checks}


def test_production_environment_with_strong_secrets_passes():
    checks = environment_checks(PRODUCTION)
    assert all(check.ok for check in checks)
    assert summarize(checks)["ready"] is True


@pytest.mark.parametrize(
    ("override", "failed"),
    [
        ({"PERSON_SEARCH_ENV": "development"}, "environment_is_production"),
        ({"PERSON_SEARCH_DEBUG": "true"}, "debug_disabled"),
        ({"PERSON_SEARCH_ALLOW_DEMO_MODELS": "1"}, "demo_models_disabled"),
        (
            {
                "PERSON_SEARCH_POSTGRES_DSN": (
                    "postgresql+psycopg://app:dev-postgres-change-me@db/app"
                )
            },
            "secret_person_search_postgres_dsn",
        ),
        ({"PERSON_SEARCH_MINIO_SECRET_KEY": "short"}, "secret_person_search_minio_secret_key"),
        ({"PERSON_SEARCH_POSTGRES_DSN": "not a url"}, "secret_person_search_postgres_dsn"),
    ],
)
def test_unsafe_environment_blocks_release(override, failed):
    checks = by_name(environment_checks({**PRODUCTION, **override}))
    assert checks[failed].ok is False and checks[failed].severity == "error"


def test_missing_rtsp_key_and_text_logs_are_warnings_only():
    checks = environment_checks(
        {**PRODUCTION, "PERSON_SEARCH_RTSP_KEY": "", "PERSON_SEARCH_LOG_FORMAT": "text"}
    )
    report = summarize(checks)
    assert report["ready"] is True and report["warnings"] == 2


def test_secret_values_never_appear_in_report():
    report = summarize(environment_checks({**PRODUCTION, "PERSON_SEARCH_MINIO_SECRET_KEY": "x"}))
    assert STRONG not in str(report) and "'x'" not in str(report)


def entry(identifier, approved=True):
    return SimpleNamespace(
        id=identifier,
        provenance=SimpleNamespace(
            license="AGPL-3.0", approved_for_project=approved, review_note="reviewed"
        ),
    )


class Registry:
    def __init__(self, mode="production", error=None, approved=True):
        self.mode = SimpleNamespace(value=mode)
        self.error = error
        self.approved = approved

    def resolve(self, detector, tracker):
        if self.error is not None:
            raise self.error
        return SimpleNamespace(
            detector=entry(detector, self.approved),
            tracker=entry(tracker),
            encoder=entry("rasa_cuhk_pedes_v1"),
        )


def test_registry_checks_cover_mode_artifacts_and_licenses():
    checks = by_name(registry_checks(lambda: Registry(), "yolo11n_coco", "bytetrack_v1"))
    assert checks["registry_production_mode"].ok
    assert checks["demo_pair_resolves"].ok
    assert checks["license_yolo11n_coco"].ok and "AGPL-3.0" in checks["license_yolo11n_coco"].detail

    demo = by_name(registry_checks(lambda: Registry(mode="demo"), "d", "t"))
    assert demo["registry_production_mode"].ok is False

    unapproved = by_name(registry_checks(lambda: Registry(approved=False), "d", "t"))
    assert unapproved["license_d"].ok is False

    broken = by_name(registry_checks(lambda: Registry(error=ValueError("sha")), "d", "t"))
    assert broken["demo_pair_resolves"].ok is False

    def failing():
        raise FileNotFoundError("/secret/path")

    assert registry_checks(failing, "d", "t")[0].ok is False
    assert "secret" not in registry_checks(failing, "d", "t")[0].detail
    assert registry_checks(lambda: None, "d", "t")[0].detail.startswith("PERSON_SEARCH_MODEL")


def test_git_checks_block_secrets_dataset_and_large_checkpoints():
    sizes = {
        "backend/config/model_artifacts/yolo11n.pt": 5 * 1024**2,
        "backend/config/model_artifacts/rasa.pth": MAX_TRACKED_MODEL_BYTES + 1,
    }
    ok = git_checks(["backend/src/app.py", "backend/config/model_artifacts/yolo11n.pt"], sizes.get)
    assert ok[0].ok

    [bad] = git_checks(
        [
            "backend/.env",
            "wildtrack-dataset/cam1.mp4",
            "backend/config/model_artifacts/rasa.pth",
            "backend/var/videos/a.mp4",
            "backend/.env.example",
        ],
        sizes.get,
    )
    assert bad.ok is False
    for path in ("backend/.env", "wildtrack-dataset/cam1.mp4", "rasa.pth", "backend/var/"):
        assert path in bad.detail
    assert "backend/.env.example" not in bad.detail
    assert git_checks(None)[0].severity == "warning"


def test_disk_check_walks_up_to_existing_directory(tmp_path):
    [check] = disk_checks(tmp_path / "missing" / "videos", 1)
    assert check.ok
    [short] = disk_checks(tmp_path, 10**18)
    assert short.ok is False
