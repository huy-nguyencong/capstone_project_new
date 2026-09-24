"""Process and storage health endpoints."""

from flask import Blueprint, current_app, jsonify

from person_search.dependencies import DependencyNotConfiguredError

health_blueprint = Blueprint("health", __name__, url_prefix="/health")


@health_blueprint.get("/live")
def liveness():
    """Report that the Flask process can accept requests."""

    return jsonify({"service": "person-search-api", "status": "ok"})


def _storage_snapshot():  # type: ignore[no-untyped-def]
    dependencies = current_app.extensions["person_search.dependencies"]
    try:
        health_service = dependencies.get("storage.health")
    except DependencyNotConfiguredError:
        return jsonify({"status": "error", "components": {}}), 503

    snapshot = health_service.check()
    return jsonify(snapshot.as_dict()), 200 if snapshot.ready else 503


@health_blueprint.get("/ready")
def readiness():  # type: ignore[no-untyped-def]
    """Report aggregate readiness without collapsing component identities."""

    return _storage_snapshot()


@health_blueprint.get("/storage")
def storage_health():  # type: ignore[no-untyped-def]
    """Expose the component-level storage snapshot for local operations."""

    return _storage_snapshot()
