"""Unit tests for Area/User/Camera model contracts."""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy.orm import attributes

from person_search.storage.postgres.models import Area, Camera, ImmutableFieldError, User
from person_search.storage.postgres.models.area import reject_area_code_change
from person_search.storage.postgres.models.camera import reject_camera_area_change

pytestmark = pytest.mark.unit


def test_identity_tables_expose_expected_constraints() -> None:
    area_constraints = {constraint.name for constraint in Area.__table__.constraints}
    user_constraints = {constraint.name for constraint in User.__table__.constraints}
    camera_constraints = {constraint.name for constraint in Camera.__table__.constraints}

    assert "uq_areas_code" in area_constraints
    assert "ck_users_role_assigned_area" in user_constraints
    assert "fk_users_assigned_area_id_areas" in user_constraints
    assert "fk_cameras_area_id_areas" in camera_constraints
    assert "ck_cameras_rtsp_no_embedded_credentials" in camera_constraints
    assert Camera.__table__.c.area_id.nullable is False
    assert User.__table__.c.assigned_area_id.nullable is True


def test_camera_area_change_is_rejected_before_flush() -> None:
    camera = Camera(code="CAM-01", name="Camera", area_id=uuid.uuid4())
    attributes.set_committed_value(camera, "area_id", camera.area_id)
    camera.area_id = uuid.uuid4()

    with pytest.raises(ImmutableFieldError, match="Camera.area_id"):
        reject_camera_area_change(None, None, camera)


def test_area_code_change_is_rejected_before_flush() -> None:
    area = Area(code="AREA-01", name="Area")
    attributes.set_committed_value(area, "code", area.code)
    area.code = "AREA-02"

    with pytest.raises(ImmutableFieldError, match="Area.code"):
        reject_area_code_change(None, None, area)
