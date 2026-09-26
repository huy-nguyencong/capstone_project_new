from __future__ import annotations

import io
import json
import os
import platform
import time
import uuid
from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pytest
import sqlalchemy as sa
from alembic import command
from alembic.config import Config
from dotenv import load_dotenv
from PIL import Image
from sqlalchemy.orm import sessionmaker

from person_search import create_app
from person_search.auth.passwords import PasswordHasher
from person_search.config import PostgresSettings, StorageSettings
from person_search.storage.milvus.client import MilvusStorage
from person_search.storage.milvus.vectors import MilvusPersonTrackIndex
from person_search.storage.minio.client import MinioStorage
from person_search.storage.minio.frames import MinioFrameStore
from person_search.storage.postgres.models import (
    AIConfigStatus,
    AIConfigVersion,
    Area,
    CaseResult,
    PersonTrack,
    TrackIndexStatus,
    User,
    UserRole,
    UserStatus,
)

load_dotenv()

pytestmark = [
    pytest.mark.e2e,
    pytest.mark.model_real(
        modules=("torch", "torchvision", "ultralytics", "lap", "transformers", "timm"),
        artifacts=("rasa_checkpoint",),
    ),
]

PASSWORD = "e2e-password"
DETECTOR_ID = "yolo11n_coco"
TRACKER_ID = "bytetrack_v1"
TEXT_QUERY = "A person walking."
ATTRIBUTES = {"upper_color": "black", "has_backpack": False}


@dataclass
class Slice:
    app: Any
    factory: sessionmaker
    users: dict[str, User]
    areas: dict[str, uuid.UUID]
    video: bytes
    timings: dict[str, float] = field(default_factory=dict)

    def client(self, name: str):
        api = self.app.test_client()
        response = api.post(
            "/api/v1/auth/login",
            json={"username": self.users[name].username, "password": PASSWORD},
        )
        assert response.status_code == 200, response.get_json()
        api.environ_base["HTTP_X_CSRF_TOKEN"] = response.json["csrf_token"]
        return api

    def timed(self, name: str):
        slice_ = self

        class Timer:
            def __enter__(self):
                self.started = time.perf_counter()

            def __exit__(self, *args):
                slice_.timings[name] = round((time.perf_counter() - self.started) * 1000, 1)

        return Timer()


def _required_environment() -> Path:
    if os.getenv("PERSON_SEARCH_RUN_E2E") != "1":
        pytest.skip("set PERSON_SEARCH_RUN_E2E=1 with a disposable database and local stack")
    for name in ("PERSON_SEARCH_MODEL_REGISTRY", "PERSON_SEARCH_E2E_VIDEO"):
        if not os.getenv(name):
            pytest.skip(f"{name} is required for the AI worker E2E slice")
    video = Path(os.environ["PERSON_SEARCH_E2E_VIDEO"]).resolve()
    if not video.is_file():
        pytest.skip("PERSON_SEARCH_E2E_VIDEO does not reference a file")
    return video


def _seed(factory) -> tuple[dict[str, User], dict[str, uuid.UUID]]:
    hasher = PasswordHasher(time_cost=1, memory_cost=1024, parallelism=1)
    suffix = uuid.uuid4().hex[:6].upper()
    with factory() as session:
        areas = {}
        for name in ("a", "b"):
            area = Area(
                id=uuid.uuid4(), code=f"E2E-AI-{name.upper()}-{suffix}", name=f"Area {name}"
            )
            session.add(area)
            areas[name] = area.id
        session.flush()
        users = {}
        for name, role, area in (
            ("admin", UserRole.ADMIN, None),
            ("operator_a", UserRole.OPERATOR, areas["a"]),
            ("operator_b", UserRole.OPERATOR, areas["b"]),
            ("viewer", UserRole.VIEWER, None),
        ):
            user = User(
                id=uuid.uuid4(),
                username=f"e2e.{name}.{suffix}".lower(),
                display_name=name,
                password_hash=hasher.hash(PASSWORD),
                role=role,
                status=UserStatus.ACTIVE,
                version=1,
                assigned_area_id=area,
            )
            session.add(user)
            users[name] = user
        session.commit()
    return users, areas


@pytest.fixture
def ai_slice() -> Iterator[Slice]:
    video = _required_environment()
    engine = sa.create_engine(PostgresSettings.from_environment(os.environ).dsn)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    alembic_config = Config("alembic.ini")
    command.downgrade(alembic_config, "base")
    command.upgrade(alembic_config, "head")
    users, areas = _seed(factory)
    app = create_app(
        {
            "TESTING": True,
            "ENVIRONMENT": "production",
            "STORAGE_ENABLED": True,
            "AUTH_COOKIE_SECURE": False,
        }
    )
    state = Slice(app, factory, users, areas, video.read_bytes())
    try:
        yield state
    finally:
        _cleanup(factory)
        engine.dispose()
        command.downgrade(alembic_config, "base")
        report = os.getenv("PERSON_SEARCH_E2E_REPORT")
        if report:
            Path(report).write_text(
                json.dumps(
                    {
                        "schema": "person-search-e2e-report/v1",
                        "python": platform.python_version(),
                        "machine": platform.machine(),
                        "timings_ms": state.timings,
                    },
                    indent=2,
                ),
                encoding="utf-8",
            )


def _cleanup(factory) -> None:
    settings = StorageSettings.from_environment()
    minio = MinioStorage(settings.minio)
    milvus = MilvusStorage(settings.milvus)
    try:
        with factory() as session:
            rows = session.execute(
                sa.select(
                    PersonTrack.id, PersonTrack.minio_object_key, PersonTrack.encoder_version
                )
            ).all()
            config = session.scalar(
                sa.select(AIConfigVersion).where(AIConfigVersion.status == AIConfigStatus.ACTIVE)
            )
        frames = MinioFrameStore(minio.client, settings.minio.bucket)
        vectors = (
            MilvusPersonTrackIndex(
                milvus.client,
                encoder_version=config.encoder_version,
                dimension=config.encoder_dimension,
            )
            if config is not None
            else None
        )
        for track_id, key, _ in rows:
            if key:
                frames.delete_frame(key)
            if vectors is not None:
                vectors.delete(track_id)
    finally:
        minio.close()
        milvus.close()


def _activate_models(admin) -> None:
    current = admin.get("/api/v1/admin/ai/config")
    assert current.status_code == 200, current.get_json()
    applied = admin.put(
        "/api/v1/admin/ai/config",
        json={
            "detector_id": DETECTOR_ID,
            "tracker_id": TRACKER_ID,
            "version": current.json["version"],
        },
    )
    assert applied.status_code == 200, applied.get_json()


def _create_camera(admin, area_id: uuid.UUID) -> str:
    created = admin.post(
        "/api/v1/admin/cameras",
        json={"code": uuid.uuid4().hex[:10], "name": "E2E AI Camera", "area_id": str(area_id)},
    )
    assert created.status_code == 201, created.get_json()
    camera_id = created.json["id"]
    enabled = admin.put(f"/api/v1/admin/cameras/{camera_id}/ai-state", json={"enabled": True})
    assert enabled.status_code == 200, enabled.get_json()
    return camera_id


def _upload(admin, camera_id: str, video: bytes) -> str:
    response = admin.post(
        f"/api/v1/admin/cameras/{camera_id}/processing-jobs",
        headers={"Idempotency-Key": uuid.uuid4().hex},
        data={
            "file": (io.BytesIO(video), "clip.mp4"),
            "recorded_started_at": "2026-09-26T08:00:00+07:00",
            "sampling_profile": "baseline",
        },
    )
    assert response.status_code == 202, response.get_json()
    return response.json["id"]


def _run_worker() -> None:
    from person_search.workers.production_main import build_worker

    worker, storage = build_worker(stopped=lambda: False)
    try:
        assert worker.run_once() is True
    finally:
        storage.close()


def _no_score(value: Any) -> None:
    assert "matching_score" not in json.dumps(value)
    assert "score" not in {key.lower() for key in _keys(value)}


def _keys(value: Any) -> set[str]:
    if isinstance(value, dict):
        return set(value) | {key for item in value.values() for key in _keys(item)}
    if isinstance(value, list):
        return {key for item in value for key in _keys(item)}
    return set()


def test_video_to_search_to_case_to_viewer_with_real_models(ai_slice: Slice) -> None:
    admin = ai_slice.client("admin")
    with ai_slice.timed("activate_models"):
        _activate_models(admin)
    camera_id = _create_camera(admin, ai_slice.areas["a"])
    job_id = _upload(admin, camera_id, ai_slice.video)

    with ai_slice.timed("worker_job"):
        _run_worker()

    job = admin.get(f"/api/v1/admin/processing-jobs/{job_id}").json
    assert job["status"] == "SUCCEEDED", job
    assert job["pipeline_mode"] == "AI"
    assert job["tracks_ready"] > 0 and job["tracks_pending"] == 0
    assert job["published_tracks"] == job["completed_tracks"] == job["tracks_ready"]
    assert job["sampling_interval"] == 10
    with ai_slice.factory() as session:
        tracks = session.scalars(
            sa.select(PersonTrack).where(PersonTrack.processing_job_id == uuid.UUID(job_id))
        ).all()
        assert tracks and all(t.index_status is TrackIndexStatus.READY for t in tracks)
        assert all(t.minio_object_key and t.vector_indexed_at for t in tracks)
        assert "matching_score" not in PersonTrack.__table__.columns

    operator = ai_slice.client("operator_a")
    with ai_slice.timed("search_text"):
        text = operator.post("/api/v1/searches/text", json={"text": TEXT_QUERY, "top_k": 8})
    assert text.status_code == 200, text.get_json()
    results = text.json["results"]
    assert results, "text search returned no READY track"
    assert all(item["camera"]["id"] == camera_id for item in results)
    assert all(isinstance(item["matching_score"], float) for item in results)

    with ai_slice.timed("search_attributes"):
        attributes = operator.post(
            "/api/v1/searches/attributes", json={"attributes": ATTRIBUTES, "top_k": 8}
        )
    assert attributes.status_code == 200, attributes.get_json()
    assert attributes.json["prompt"].startswith("A person ")
    assert all(isinstance(item["matching_score"], float) for item in attributes.json["results"])

    target = results[0]
    frame = operator.get(target["frame_url"])
    assert frame.status_code == 200 and frame.mimetype == "image/jpeg"
    bbox = target["bbox"]
    with Image.open(io.BytesIO(frame.data)) as image:
        assert image.size == (bbox["frame_width"], bbox["frame_height"])
        crop = image.crop(
            (bbox["x"], bbox["y"], bbox["x"] + bbox["width"], bbox["y"] + bbox["height"])
        )
        query = io.BytesIO()
        crop.save(query, format="PNG")
    with ai_slice.timed("search_image"):
        by_image = operator.post(
            "/api/v1/searches/image",
            data={"image": (io.BytesIO(query.getvalue()), "query.png", "image/png"), "top_k": "8"},
            content_type="multipart/form-data",
        )
    assert by_image.status_code == 200, by_image.get_json()
    ranked = [item["track_id"] for item in by_image.json["results"]]
    assert target["track_id"] in ranked[:4]
    assert operator.get(target["crop_url"]).status_code == 200

    outsider = ai_slice.client("operator_b")
    isolated = outsider.post("/api/v1/searches/text", json={"text": TEXT_QUERY, "top_k": 8})
    assert isolated.status_code == 200
    assert all(item["camera"]["id"] != camera_id for item in isolated.json["results"])
    assert outsider.get(target["frame_url"]).status_code in {403, 404}

    created = operator.post(
        "/api/v1/cases", json={"title": "E2E AI case", "track_id": target["track_id"]}
    )
    assert created.status_code == 201, created.get_json()
    case_id = created.json["case"]["id"]
    _no_score(created.json)
    with ai_slice.factory() as session:
        assert "matching_score" not in CaseResult.__table__.columns
        assert session.scalar(sa.select(sa.func.count()).select_from(CaseResult)) == 1

    viewer = ai_slice.client("viewer")
    for client in (operator, viewer):
        detail = client.get(f"/api/v1/cases/{case_id}")
        assert detail.status_code == 200, detail.get_json()
        _no_score(detail.json)
        [result] = detail.json["results"]
        assert result["track_id"] == target["track_id"]
        assert result["bbox"] == bbox
        for url in (result["crop_url"], result["frame_url"]):
            image = client.get(url)
            assert image.status_code == 200 and image.mimetype == "image/jpeg"
    assert viewer.post("/api/v1/searches/text", json={"text": TEXT_QUERY}).status_code == 403
