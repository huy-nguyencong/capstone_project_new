"""Phase 3 API tests. Use only an explicitly supplied, migrated disposable database."""

import copy
import json
import os
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest
from cryptography.fernet import Fernet
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from person_search import create_app
from person_search.ai.registry import registry_from_dict
from person_search.auth.passwords import PasswordHasher
from person_search.dependencies import DependencyContainer
from person_search.services.auth import AuthService
from person_search.services.camera_runtime import CameraRuntime
from person_search.services.cameras import CameraService
from person_search.storage.postgres.models import (
    AIConfigStatus,
    AIConfigVersion,
    Area,
    AuditLog,
    Camera,
    User,
    UserRole,
    UserStatus,
)
from person_search.storage.postgres.unit_of_work import UnitOfWork

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        not os.getenv("PERSON_SEARCH_CAMERA_TEST_DSN"),
        reason="requires disposable camera test database",
    ),
]


@pytest.fixture
def world():
    engine = create_engine(os.environ["PERSON_SEARCH_CAMERA_TEST_DSN"])
    factory = sessionmaker(engine, expire_on_commit=False)

    def uow():
        return UnitOfWork(factory)

    hasher = PasswordHasher(time_cost=1, memory_cost=1024, parallelism=1)
    suffix = uuid.uuid4().hex[:8]
    with uow() as work:
        area = Area(id=uuid.uuid4(), code=f"A-{suffix.upper()}", name="Gate A")
        work.session.add(area)
        work.flush()
        users = {}
        for role in UserRole:
            row = User(
                id=uuid.uuid4(),
                username=f"{role.value.lower()}.{suffix}",
                display_name=role.value,
                password_hash=hasher.hash("test-password"),
                role=role,
                status=UserStatus.ACTIVE,
                version=1,
                assigned_area_id=area.id if role == UserRole.OPERATOR else None,
            )
            work.session.add(row)
            users[role] = row
        work.commit()
    config_root = Path(__file__).parents[2] / "config"
    registry_payload = json.loads((config_root / "models.demo.json").read_text(encoding="utf-8"))
    alternate = copy.deepcopy(registry_payload["detectors"][0])
    alternate["id"] = "demo_detector_alt"
    alternate["display_name"] = "Alternate synthetic detector"
    registry_payload["detectors"].append(alternate)
    registry = registry_from_dict(registry_payload, artifact_root=config_root, allow_demo=True)
    runtime = CameraRuntime(Fernet.generate_key().decode(), ["10.0.0.0/8"])
    service = CameraService(uow, runtime, registry)
    deps = DependencyContainer()
    deps.register("auth.service", AuthService(uow, hasher=hasher))
    deps.register("cameras.service", service)
    app = create_app({"TESTING": True}, dependencies=deps)
    yield app, service, users, area.id, factory
    engine.dispose()


def client(world, role=UserRole.ADMIN):
    app, _, users, _, _ = world
    api = app.test_client()
    response = api.post(
        "/api/v1/auth/login", json={"username": users[role].username, "password": "test-password"}
    )
    api.environ_base["HTTP_X_CSRF_TOKEN"] = response.json["csrf_token"]
    return api


def create_camera(api, area, **extra):
    return api.post(
        "/api/v1/admin/cameras",
        json={"code": uuid.uuid4().hex[:10], "name": "Gate Camera", "area_id": str(area), **extra},
    )


def test_camera_lifecycle_and_privacy(world):
    api = client(world)
    _, service, _, area, factory = world
    created = create_camera(api, area)
    assert created.status_code == 201
    row = created.json
    path = f"/api/v1/admin/cameras/{row['id']}"
    assert row["version"] == 1 and not row["has_rtsp"]
    assert api.post(path + "/connection-tests").json["error"]["code"] == "camera_has_no_rtsp"
    assert api.patch(path, json={"area_id": str(area), "version": 1}).status_code == 422
    assert api.patch(path, json={"name": "New", "version": 0}).status_code == 409
    patched = api.patch(path, json={"version": 1, "rtsp_url": "rtsp://admin:secret@10.0.0.1/live"})
    assert patched.status_code == 200
    assert "secret" not in patched.text and "admin:" not in patched.text
    assert patched.json["rtsp_url_masked"] == "rtsp://***@10.0.0.1/live"
    service.runtime.probe = lambda *args: "OFFLINE"
    assert api.post(path + "/connection-tests").json["rtsp_status"] == "OFFLINE"
    duplicate = create_camera(api, area, code=row["code"])
    assert duplicate.status_code == 409
    assert api.post(path + "/retire").json["status"] == "RETIRED"
    assert api.put(path + "/ai-state", json={"enabled": True}).status_code == 409
    assert api.get(path).status_code == 200
    with factory() as session:
        stored = session.get(Camera, uuid.UUID(row["id"]))
        assert stored.rtsp_credentials != "admin:secret"
        audits = session.scalars(select(AuditLog).where(AuditLog.target_id == stored.id)).all()
        assert len(audits) == 4
        assert all("secret" not in str(a.event_metadata) for a in audits)


def test_permissions_and_csrf_all_routes(world):
    camera_id = uuid.uuid4()
    routes = [
        ("GET", "/cameras"),
        ("POST", "/cameras"),
        ("GET", f"/cameras/{camera_id}"),
        ("PATCH", f"/cameras/{camera_id}"),
        ("POST", f"/cameras/{camera_id}/retire"),
        ("POST", f"/cameras/{camera_id}/connection-tests"),
        ("PUT", f"/cameras/{camera_id}/ai-state"),
        ("GET", "/ai/models"),
        ("GET", "/ai/config"),
        ("PUT", "/ai/config"),
    ]
    for role in (None, UserRole.OPERATOR, UserRole.VIEWER):
        api = world[0].test_client() if role is None else client(world, role)
        for method, path in routes:
            assert api.open("/api/v1/admin" + path, method=method, json={}).status_code == (
                401 if role is None else 403
            )
    api = client(world)
    api.environ_base.pop("HTTP_X_CSRF_TOKEN")
    for method, path in routes:
        if method != "GET":
            assert api.open("/api/v1/admin" + path, method=method, json={}).status_code == 403


def test_config_rollback_versions_ai_idempotency_and_pagination(world):
    api = client(world)
    _, service, users, area, factory = world
    before = api.get("/api/v1/admin/ai/config").json
    config = {
        "detector_id": "demo_detector",
        "tracker_id": "demo_tracker",
        "version": before["version"],
    }
    assert (
        api.put("/api/v1/admin/ai/config", json={**config, "detector_id": "unknown"}).status_code
        == 422
    )
    incompatible = {**config, "detector_id": "demo_detector_alt"}
    assert (
        api.put("/api/v1/admin/ai/config", json=incompatible).json["error"]["code"]
        == "incompatible_model_pair"
    )
    applied = api.put("/api/v1/admin/ai/config", json=config)
    assert applied.status_code == 200
    assert api.put("/api/v1/admin/ai/config", json=config).status_code == 409
    config["version"] = applied.json["version"]

    def fail(_):
        raise RuntimeError("model failed")

    service.apply_config = fail
    assert api.put("/api/v1/admin/ai/config", json=config).status_code == 503
    assert api.get("/api/v1/admin/ai/config").json == applied.json
    service.apply_config = lambda _: None
    with ThreadPoolExecutor(max_workers=2) as pool:

        def apply(_):
            from person_search.api.errors import ApiError

            try:
                service.configure(config, users[UserRole.ADMIN].id)
                return 200
            except ApiError as error:
                return error.status

        assert sorted(pool.map(apply, range(2))) == [200, 409]
    row = create_camera(api, area).json
    path = f"/api/v1/admin/cameras/{row['id']}/ai-state"
    enabled = api.put(path, json={"enabled": True})
    assert enabled.status_code == 200
    assert "worker_state" not in enabled.json
    assert api.put(path, json={"enabled": True}).json["version"] == enabled.json["version"]
    assert api.put(path, json={"enabled": "true"}).status_code == 422
    assert not api.put(path, json={"enabled": False}).json["ai_enabled"]
    create_camera(api, area)
    page = api.get("/api/v1/admin/cameras", query_string={"area_id": str(area), "limit": 1}).json
    next_page = api.get(
        "/api/v1/admin/cameras",
        query_string={"area_id": str(area), "limit": 1, "cursor": page["next_cursor"]},
    ).json
    assert page["items"][0]["id"] != next_page["items"][0]["id"]
    assert next_page["next_cursor"] is None
    with factory() as session:
        assert (
            len(
                session.scalars(
                    select(AIConfigVersion).where(AIConfigVersion.status == AIConfigStatus.ACTIVE)
                ).all()
            )
            == 1
        )


def test_missing_config_and_stale_probe(world):
    from person_search.api.errors import ApiError

    api = client(world)
    _, service, users, area, _ = world
    row = create_camera(api, area, rtsp_url="rtsp://10.0.0.1/live").json
    path = f"/api/v1/admin/cameras/{row['id']}"
    original_active = service.active
    service.active = lambda work: None
    assert (
        api.put(path + "/ai-state", json={"enabled": True}).json["error"]["code"]
        == "ai_config_missing"
    )
    service.active = original_active

    def concurrent_edit(*args):
        service.save(
            {"name": "Changed during probe", "version": row["version"]},
            users[UserRole.ADMIN].id,
            row["id"],
        )
        return "ONLINE"

    service.runtime.probe = concurrent_edit
    result = api.post(path + "/connection-tests")
    assert result.status_code == 409
    assert api.get(path).json["rtsp_status"] == "UNKNOWN"
    assert api.get(path).json["last_checked_at"] is None
    for invalid in ("0", "101", "bad"):
        assert api.get("/api/v1/admin/cameras", query_string={"limit": invalid}).status_code == 422
    assert api.get("/api/v1/admin/cameras?cursor=invalid!").status_code == 422
    assert api.patch(path, json=[]).status_code == 400
    assert api.get(f"/api/v1/admin/cameras/{uuid.uuid4()}").status_code == 404
    with pytest.raises(ApiError):
        service.configure(
            {"detector_id": "unknown", "tracker_id": "unknown", "version": None},
            users[UserRole.ADMIN].id,
        )
