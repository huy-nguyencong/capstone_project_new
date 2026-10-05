"""The application server can serve the built web application in place of the Vite dev server."""

from __future__ import annotations

from pathlib import Path

import pytest

from person_search.app import create_app

pytestmark = pytest.mark.unit


@pytest.fixture
def dist(tmp_path: Path) -> Path:
    root = tmp_path / "dist"
    (root / "assets").mkdir(parents=True)
    (root / "index.html").write_text("<!doctype html><title>Person search</title>", "utf-8")
    (root / "assets" / "index-abc123.js").write_text("console.log('app')", "utf-8")
    (root / "favicon.svg").write_text("<svg/>", "utf-8")
    (tmp_path / "secret.txt").write_text("outside", "utf-8")
    return root


def _app(dist: Path | None):
    # The local .env may point at frontend/dist; the test decides explicitly.
    config = {"TESTING": True, "ENVIRONMENT": "testing", "STATIC_FRONTEND_DIR": ""}
    if dist is not None:
        config["STATIC_FRONTEND_DIR"] = str(dist)
    return create_app(config)


def test_without_configuration_the_root_is_not_served() -> None:
    client = _app(None).test_client()

    assert client.get("/").status_code == 404
    assert client.get("/health/live").status_code == 200


def test_index_and_client_routes_return_the_page_with_a_page_policy(dist: Path) -> None:
    client = _app(dist).test_client()

    for path in ("/", "/cases", "/admin/cameras/42"):
        response = client.get(path)
        assert response.status_code == 200, path
        assert b"Person search" in response.data
        assert response.headers["Cache-Control"] == "no-cache"
        assert "script-src 'self'" in response.headers["Content-Security-Policy"]
        assert "frame-ancestors 'none'" in response.headers["Content-Security-Policy"]
        assert response.headers["X-Frame-Options"] == "DENY"


def test_hashed_assets_are_cacheable_and_other_files_are_served(dist: Path) -> None:
    client = _app(dist).test_client()

    asset = client.get("/assets/index-abc123.js")
    assert asset.status_code == 200
    assert asset.data == b"console.log('app')"
    assert asset.headers["Cache-Control"] == "public, max-age=31536000, immutable"
    favicon = client.get("/favicon.svg")
    assert favicon.status_code == 200
    assert favicon.data == b"<svg/>"
    assert "Cache-Control" not in favicon.headers or favicon.headers["Cache-Control"] != (
        "public, max-age=31536000, immutable"
    )


def test_api_and_health_paths_never_fall_back_to_the_page(dist: Path) -> None:
    client = _app(dist).test_client()

    missing = client.get("/api/v1/does-not-exist")
    assert missing.status_code == 404
    assert b"Person search" not in missing.data
    assert client.get("/health/live").status_code == 200
    assert client.get("/api").status_code == 404


def test_paths_outside_the_directory_are_not_served(dist: Path) -> None:
    client = _app(dist).test_client()

    response = client.get("/../secret.txt")
    assert response.status_code in (200, 404)
    assert b"outside" not in response.data
    response = client.get("/assets/../../secret.txt")
    assert b"outside" not in response.data


def test_missing_index_is_a_configuration_error(tmp_path: Path) -> None:
    with pytest.raises(RuntimeError, match="index.html"):
        _app(tmp_path)
