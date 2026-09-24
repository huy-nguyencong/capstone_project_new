"""Shared pytest fixtures."""

import pytest

from person_search import create_app


@pytest.fixture
def app():
    """Create an isolated Flask app for each test."""

    return create_app({"TESTING": True, "ENVIRONMENT": "testing"})


@pytest.fixture
def client(app):  # type: ignore[no-untyped-def]
    """Return Flask's in-process HTTP client."""

    return app.test_client()
