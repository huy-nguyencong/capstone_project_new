"""Shared pytest fixtures."""

import importlib.util
import os
from pathlib import Path

import pytest

from person_search import create_app

MODEL_ARTIFACTS = {
    "rasa_checkpoint": Path(__file__).parents[1]
    / "config"
    / "model_artifacts"
    / "rasa_cuhk_pedes_v1.pth",
}


def _missing_model_requirements(marker):
    missing = [
        f"package:{name}"
        for name in marker.kwargs.get("modules", ())
        if importlib.util.find_spec(name) is None
    ]
    missing += [
        f"artifact:{name}"
        for name in marker.kwargs.get("artifacts", ())
        if not MODEL_ARTIFACTS[name].is_file()
    ]
    return missing


def pytest_collection_modifyitems(config, items):
    required = os.getenv("PERSON_SEARCH_REQUIRE_MODEL_TESTS") == "1"
    for item in items:
        marker = item.get_closest_marker("model_real")
        if marker is None or required:
            continue
        missing = _missing_model_requirements(marker)
        if missing:
            item.add_marker(
                pytest.mark.skip(reason="model_real prerequisites missing: " + ", ".join(missing))
            )


@pytest.fixture
def app():
    """Create an isolated Flask app for each test."""

    return create_app({"TESTING": True, "ENVIRONMENT": "testing"})


@pytest.fixture
def client(app):  # type: ignore[no-untyped-def]
    """Return Flask's in-process HTTP client."""

    return app.test_client()
