"""Tests for typed storage settings and secret-safe health reporting."""

from __future__ import annotations

import json
import logging

import pytest

from person_search import create_app
from person_search.config import ConfigurationError, StorageSettings
from person_search.storage.health import StorageHealthService, redact_text

pytestmark = pytest.mark.unit


def valid_environment() -> dict[str, str]:
    return {
        "PERSON_SEARCH_POSTGRES_DSN": (
            "postgresql+psycopg://person_search:postgres-secret@localhost:5432/person_search"
        ),
        "PERSON_SEARCH_MILVUS_URI": "http://localhost:19530",
        "PERSON_SEARCH_MILVUS_TOKEN": "milvus-secret",
        "PERSON_SEARCH_MINIO_ENDPOINT": "localhost:9000",
        "PERSON_SEARCH_MINIO_ACCESS_KEY": "app-access-key",
        "PERSON_SEARCH_MINIO_SECRET_KEY": "minio-secret",
    }


def test_storage_settings_parse_defaults_and_redact_all_secrets() -> None:
    settings = StorageSettings.from_environment(valid_environment())

    assert settings.postgres.pool_size == 5
    assert settings.postgres.max_overflow == 5
    assert settings.milvus.database == "default"
    assert settings.minio.bucket == "person-search-frames"
    assert settings.minio.secure is False

    rendered = json.dumps(settings.redacted())
    for secret in ("postgres-secret", "milvus-secret", "app-access-key", "minio-secret"):
        assert secret not in rendered


@pytest.mark.parametrize(
    ("name", "value", "message"),
    [
        ("PERSON_SEARCH_POSTGRES_DSN", "sqlite:///local.db", r"postgresql\+psycopg"),
        ("PERSON_SEARCH_POSTGRES_POOL_SIZE", "many", "must be an integer"),
        ("PERSON_SEARCH_MINIO_SECURE", "perhaps", "must be a boolean"),
    ],
)
def test_storage_settings_reject_invalid_values(name: str, value: str, message: str) -> None:
    environment = valid_environment()
    environment[name] = value

    with pytest.raises(ConfigurationError, match=message):
        StorageSettings.from_environment(environment)


def test_storage_settings_report_missing_variable_without_values() -> None:
    environment = valid_environment()
    del environment["PERSON_SEARCH_MINIO_SECRET_KEY"]

    with pytest.raises(ConfigurationError) as error:
        StorageSettings.from_environment(environment)

    assert "PERSON_SEARCH_MINIO_SECRET_KEY" in str(error.value)
    assert "minio-secret" not in str(error.value)


def test_development_application_fails_fast_when_storage_config_is_missing(
    monkeypatch,
) -> None:  # type: ignore[no-untyped-def]
    for name in valid_environment():
        monkeypatch.delenv(name, raising=False)

    with pytest.raises(ConfigurationError, match="PERSON_SEARCH_POSTGRES_DSN"):
        create_app({"ENVIRONMENT": "development"})


class Probe:
    def __init__(self, name: str, error: Exception | None = None) -> None:
        self.name = name
        self.error = error

    def check_health(self) -> None:
        if self.error:
            raise self.error


def test_health_service_isolates_component_failure_and_redacts_log(caplog) -> None:  # type: ignore[no-untyped-def]
    secret = "do-not-log-this"
    service = StorageHealthService(
        (Probe("postgres"), Probe("milvus", RuntimeError(f"failed with {secret}"))),
        secrets=(secret,),
    )

    with caplog.at_level(logging.WARNING):
        snapshot = service.check()

    assert snapshot.ready is False
    assert snapshot.components == {
        "postgres": {"status": "ok"},
        "milvus": {"status": "error", "error": "unavailable"},
    }
    assert secret not in caplog.text
    assert "failed with ***" in caplog.text


def test_redact_text_ignores_empty_values() -> None:
    assert redact_text("safe", ("",)) == "safe"
