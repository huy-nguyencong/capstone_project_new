"""Version 1 API blueprint."""

from flask import Blueprint

from person_search.api.v1.auth import auth_blueprint
from person_search.api.v1.cameras import admin_cameras_blueprint
from person_search.api.v1.cases import cases_blueprint
from person_search.api.v1.jobs import admin_jobs_blueprint
from person_search.api.v1.monitor import monitor_blueprint
from person_search.api.v1.searches import search_blueprint
from person_search.api.v1.users import admin_users_blueprint, areas_blueprint
from person_search.api.v1.viewer import viewer_blueprint

api_v1_blueprint = Blueprint("api_v1", __name__)
api_v1_blueprint.register_blueprint(auth_blueprint)
api_v1_blueprint.register_blueprint(admin_jobs_blueprint)
api_v1_blueprint.register_blueprint(admin_cameras_blueprint)
api_v1_blueprint.register_blueprint(areas_blueprint)
api_v1_blueprint.register_blueprint(admin_users_blueprint)
api_v1_blueprint.register_blueprint(search_blueprint)
api_v1_blueprint.register_blueprint(cases_blueprint)
api_v1_blueprint.register_blueprint(viewer_blueprint)
api_v1_blueprint.register_blueprint(monitor_blueprint)
