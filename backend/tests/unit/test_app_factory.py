"""Smoke tests for the BE-00 application skeleton."""

import pytest

from person_search import create_app
from person_search.config import config_for_environment, parse_boolean_environment
from person_search.dependencies import DependencyContainer, DependencyNotConfiguredError
from person_search.storage.health import StorageHealthService

pytestmark = pytest.mark.unit


def test_application_factory_creates_isolated_instances() -> None:
    first = create_app({"TESTING": True, "CUSTOM_VALUE": "first"})
    second = create_app({"TESTING": True, "CUSTOM_VALUE": "second"})

    assert first is not second
    assert first.config["CUSTOM_VALUE"] == "first"
    assert second.config["CUSTOM_VALUE"] == "second"


def test_liveness_endpoint(client) -> None:  # type: ignore[no-untyped-def]
    response = client.get("/health/live")

    assert response.status_code == 200
    assert response.get_json() == {"service": "person-search-api", "status": "ok"}


def test_readiness_is_ok_when_storage_is_explicitly_disabled(client) -> None:  # type: ignore[no-untyped-def]
    response = client.get("/health/ready")

    assert response.status_code == 200
    assert response.get_json() == {"status": "ok", "components": {}}


def test_readiness_reports_exact_failing_component() -> None:
    class FailingProbe:
        name = "milvus"

        def check_health(self) -> None:
            raise RuntimeError("offline")

    container = DependencyContainer()
    container.register("storage.health", StorageHealthService((FailingProbe(),)))
    app = create_app({"TESTING": True}, dependencies=container)

    response = app.test_client().get("/health/storage")

    assert response.status_code == 503
    assert response.get_json() == {
        "status": "error",
        "components": {"milvus": {"status": "error", "error": "unavailable"}},
    }


def test_versioned_ping_endpoint(client) -> None:  # type: ignore[no-untyped-def]
    response = client.get("/api/v1/ping")

    assert response.status_code == 200
    assert response.get_json() == {"status": "ok", "version": "v1"}


def test_api_not_found_uses_json_error(client) -> None:  # type: ignore[no-untyped-def]
    response = client.get("/api/v1/does-not-exist")

    assert response.status_code == 404
    assert response.get_json() == {
        "error": {
            "code": "not_found",
            "message": "The requested URL was not found on the server. If you entered the URL "
            "manually please check your spelling and try again.",
        }
    }


def test_dependency_container_can_be_injected() -> None:
    container = DependencyContainer()
    fake_clock = object()
    container.register("clock", fake_clock)

    app = create_app({"TESTING": True}, dependencies=container)

    assert app.extensions["person_search.dependencies"].get("clock") is fake_clock


def test_dependency_container_rejects_missing_and_duplicate_values() -> None:
    container = DependencyContainer()

    with pytest.raises(DependencyNotConfiguredError):
        container.get("missing")

    container.register("clock", object())
    with pytest.raises(ValueError, match="already registered"):
        container.register("clock", object())


def test_unknown_environment_fails_fast() -> None:
    with pytest.raises(ValueError, match="Unsupported PERSON_SEARCH_ENV"):
        config_for_environment("unknown")


@pytest.mark.parametrize("value", ["1", "true", "YES", "on"])
def test_parse_boolean_environment_accepts_true_values(monkeypatch, value: str) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setenv("FEATURE_ENABLED", value)

    assert parse_boolean_environment("FEATURE_ENABLED") is True


@pytest.mark.parametrize("value", ["0", "false", "NO", "off"])
def test_parse_boolean_environment_accepts_false_values(monkeypatch, value: str) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setenv("FEATURE_ENABLED", value)

    assert parse_boolean_environment("FEATURE_ENABLED", default=True) is False


def test_parse_boolean_environment_rejects_unknown_value(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setenv("FEATURE_ENABLED", "sometimes")

    with pytest.raises(ValueError, match="must be a boolean"):
        parse_boolean_environment("FEATURE_ENABLED")
