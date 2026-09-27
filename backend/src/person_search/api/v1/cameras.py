from flask import Blueprint, current_app, jsonify, request

from person_search.api.errors import ApiError
from person_search.api.rate_limit import rate_limited
from person_search.api.v1.users import _json_body
from person_search.auth.web import current_actor, require_auth
from person_search.storage.postgres.models import UserRole

admin_cameras_blueprint = Blueprint("admin_cameras", __name__, url_prefix="/admin")


def service():
    return current_app.extensions["person_search.dependencies"].get("cameras.service")


@admin_cameras_blueprint.get("/cameras")
@require_auth(UserRole.ADMIN)
def list_cameras():
    return jsonify(service().list(request.args))


@admin_cameras_blueprint.post("/cameras")
@require_auth(UserRole.ADMIN)
def create_camera():
    return jsonify(service().save(_json_body(), current_actor().id)), 201


@admin_cameras_blueprint.get("/cameras/<uuid:camera_id>")
@require_auth(UserRole.ADMIN)
def get_camera(camera_id):
    return jsonify(service().get(camera_id))


@admin_cameras_blueprint.patch("/cameras/<uuid:camera_id>")
@require_auth(UserRole.ADMIN)
def update_camera(camera_id):
    return jsonify(service().save(_json_body(), current_actor().id, camera_id))


@admin_cameras_blueprint.post("/cameras/<uuid:camera_id>/retire")
@require_auth(UserRole.ADMIN)
def retire_camera(camera_id):
    return jsonify(service().transition(camera_id, current_actor().id))


@admin_cameras_blueprint.post("/cameras/<uuid:camera_id>/reactivate")
@require_auth(UserRole.ADMIN)
def reactivate_camera(camera_id):
    return jsonify(service().reactivate(camera_id, current_actor().id))


@admin_cameras_blueprint.post("/cameras/<uuid:camera_id>/connection-tests")
@require_auth(UserRole.ADMIN)
@rate_limited("connection_test")
def test_camera(camera_id):
    return jsonify(service().test(camera_id, current_actor().id))


@admin_cameras_blueprint.put("/cameras/<uuid:camera_id>/ai-state")
@require_auth(UserRole.ADMIN)
def ai_state(camera_id):
    body = _json_body()
    if set(body) != {"enabled"} or type(body["enabled"]) is not bool:
        raise ApiError(422, "invalid_enabled", "enabled phải là boolean.")
    return jsonify(service().transition(camera_id, current_actor().id, body["enabled"]))


@admin_cameras_blueprint.get("/ai/models")
@require_auth(UserRole.ADMIN)
def models():
    return jsonify(service().models())


@admin_cameras_blueprint.get("/ai/config")
@require_auth(UserRole.ADMIN)
def config():
    return jsonify(service().config())


@admin_cameras_blueprint.put("/ai/config")
@require_auth(UserRole.ADMIN)
def configure():
    return jsonify(service().configure(_json_body(), current_actor().id))
