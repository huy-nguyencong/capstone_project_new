from flask import Blueprint, current_app, jsonify, request

from person_search.api.errors import ApiError
from person_search.auth.web import current_actor, require_auth
from person_search.storage.postgres.models import UserRole

admin_jobs_blueprint = Blueprint("admin_jobs", __name__, url_prefix="/admin")


def service():
    return current_app.extensions["person_search.dependencies"].get("jobs.service")


@admin_jobs_blueprint.post("/cameras/<uuid:camera_id>/processing-jobs")
@require_auth(UserRole.ADMIN)
def upload_job(camera_id):
    if len(request.files.getlist("file")) != 1 or set(request.files) != {"file"}:
        raise ApiError(422, "file_required", "Chỉ chọn một file video.")
    if any(len(request.form.getlist(key)) != 1 for key in request.form):
        raise ApiError(422, "invalid_fields", "Trường upload bị trùng.")
    return jsonify(
        service().upload(
            camera_id,
            current_actor().id,
            request.headers.get("Idempotency-Key"),
            request.form,
            request.files.get("file"),
        )
    ), 202


@admin_jobs_blueprint.get("/processing-jobs")
@require_auth(UserRole.ADMIN)
def list_jobs():
    return jsonify(service().list(request.args))


@admin_jobs_blueprint.get("/processing-jobs/<uuid:job_id>")
@require_auth(UserRole.ADMIN)
def get_job(job_id):
    return jsonify(service().get(job_id))


@admin_jobs_blueprint.post("/processing-jobs/<uuid:job_id>/cancel")
@require_auth(UserRole.ADMIN)
def cancel_job(job_id):
    return jsonify(service().cancel(job_id, current_actor().id))
