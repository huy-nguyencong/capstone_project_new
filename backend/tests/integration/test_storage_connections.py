"""Real connection smoke test for the local Docker storage stack."""

from __future__ import annotations

import os

import pytest
from dotenv import load_dotenv

from person_search import create_app
from person_search.config import StorageSettings
from person_search.storage.runtime import StorageRuntime

load_dotenv()

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        os.getenv("PERSON_SEARCH_RUN_INTEGRATION") != "1",
        reason="set PERSON_SEARCH_RUN_INTEGRATION=1 with the local storage stack running",
    ),
]


def test_all_storage_connections_open_check_and_close() -> None:
    runtime = StorageRuntime.from_settings(StorageSettings.from_environment())
    try:
        snapshot = runtime.health.check()
        assert snapshot.ready is True
        assert snapshot.components == {
            "postgres": {"status": "ok"},
            "milvus": {"status": "ok"},
            "minio": {"status": "ok"},
        }
    finally:
        runtime.close()


def test_application_readiness_uses_all_real_storage_components() -> None:
    app = create_app({"ENVIRONMENT": "development", "TESTING": True})
    try:
        response = app.test_client().get("/health/ready")
        assert response.status_code == 200
        assert response.get_json() == {
            "status": "ok",
            "components": {
                "postgres": {"status": "ok"},
                "milvus": {"status": "ok"},
                "minio": {"status": "ok"},
            },
        }
    finally:
        app.extensions["person_search.storage_runtime"].close()


def test_readiness_identifies_expected_unavailable_component() -> None:
    expected = os.getenv("PERSON_SEARCH_EXPECT_UNHEALTHY_COMPONENT")
    if not expected:
        pytest.skip("set PERSON_SEARCH_EXPECT_UNHEALTHY_COMPONENT for failure injection")

    app = create_app({"ENVIRONMENT": "development", "TESTING": True})
    try:
        response = app.test_client().get("/health/ready")
        payload = response.get_json()

        assert response.status_code == 503
        assert payload["status"] == "error"
        assert payload["components"][expected] == {
            "status": "error",
            "error": "unavailable",
        }
        assert all(
            state["status"] == "ok"
            for name, state in payload["components"].items()
            if name != expected
        )
    finally:
        app.extensions["person_search.storage_runtime"].close()
