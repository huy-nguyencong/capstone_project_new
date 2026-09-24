"""Version 1 API blueprint."""

from flask import Blueprint, jsonify

api_v1_blueprint = Blueprint("api_v1", __name__)


@api_v1_blueprint.get("/ping")
def ping():
    """Provide a stable smoke endpoint while business routes are not implemented."""

    return jsonify({"status": "ok", "version": "v1"})
