"""Smoke tests for the storage package boundaries created by STO-00."""

from importlib import import_module

import pytest

from person_search import create_app
from person_search.dependencies import DependencyContainer

pytestmark = pytest.mark.unit


@pytest.mark.parametrize(
    "module_name",
    [
        "person_search.domain",
        "person_search.services",
        "person_search.storage",
        "person_search.storage.postgres",
        "person_search.storage.milvus",
        "person_search.storage.minio",
    ],
)
def test_storage_boundaries_are_importable_without_external_services(
    module_name: str,
) -> None:
    module = import_module(module_name)

    assert module is not None


def test_app_factory_does_not_require_storage_connections() -> None:
    app = create_app({"TESTING": True, "ENVIRONMENT": "testing"})

    assert app.config["TESTING"] is True
    assert isinstance(
        app.extensions["person_search.dependencies"],
        DependencyContainer,
    )
