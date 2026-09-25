"""Version 1 API blueprint."""

from flask import Blueprint, jsonify

from person_search.api.v1.auth import auth_blueprint
from person_search.api.v1.cameras import admin_cameras_blueprint
from person_search.api.v1.jobs import admin_jobs_blueprint
from person_search.api.v1.users import admin_users_blueprint, areas_blueprint

api_v1_blueprint = Blueprint("api_v1", __name__)
api_v1_blueprint.register_blueprint(auth_blueprint)
api_v1_blueprint.register_blueprint(admin_jobs_blueprint)
api_v1_blueprint.register_blueprint(admin_cameras_blueprint)
api_v1_blueprint.register_blueprint(areas_blueprint)
api_v1_blueprint.register_blueprint(admin_users_blueprint)


@api_v1_blueprint.get("/ping")
def ping():
    """Provide a stable smoke endpoint while business routes are not implemented."""

    return jsonify({"status": "ok", "version": "v1"})
