"""Process-level health endpoints."""

from flask import Blueprint, jsonify

health_blueprint = Blueprint("health", __name__, url_prefix="/health")


@health_blueprint.get("/live")
def liveness():
    """Report that the Flask process can accept requests."""

    return jsonify({"service": "person-search-api", "status": "ok"})
