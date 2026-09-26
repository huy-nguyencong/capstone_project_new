import os
import uuid
from types import SimpleNamespace

import pytest
from PIL import Image
from sqlalchemy import func, select
from test_camera_admin import world as world
from test_video_jobs import setup as setup

from person_search.services.diagnostics import DiagnosticSettings, ProductionDiagnostics
from person_search.services.monitoring import MonitoringService
from person_search.storage.contracts import BoundingBoxPixels
from person_search.storage.postgres.models import (
    AIConfigStatus,
    AIConfigVersion,
    AuditLog,
    Camera,
    PersonTrack,
    ProcessingJob,
    StorageOutboxEvent,
)
from person_search.storage.postgres.unit_of_work import UnitOfWork
from person_search.workers.contracts import (
    Detection,
    ModelLineage,
    SourceFrame,
    TrackState,
    TrackUpdate,
)

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        not os.getenv("PERSON_SEARCH_CAMERA_TEST_DSN"), reason="requires disposable database"
    ),
]

LINEAGE = ModelLineage("component", "1", "a" * 64)


def unit_vector(dimension):
    return [1.0] + [0.0] * (dimension - 1)


class Lifecycle:
    def open(self):
        return None

    def close(self):
        return None


class Detector(Lifecycle):
    def detect(self, frame):
        box = BoundingBoxPixels(4, 4, 20, 30, frame.width, frame.height)
        return (Detection(box, 0, "person", 0.9, LINEAGE),)


class Tracker(Lifecycle):
    def update(self, frame, detections):
        return tuple(
            TrackUpdate(
                "bt-1",
                frame.camera_id,
                item.bbox,
                frame.source_frame_index,
                frame.source_timestamp_ms,
                TrackState.ACTIVE,
                LINEAGE,
            )
            for item in detections
        )

    def flush(self):
        return ()


class Encoder(Lifecycle):
    def __init__(self, dimension):
        self.dimension = dimension

    def encode(self, crop):
        return SimpleNamespace(values=tuple(unit_vector(self.dimension)))


class Gateway(Lifecycle):
    def __init__(self, dimension):
        self.dimension = dimension

    def image(self, content, *, version, dimension):
        return unit_vector(dimension)

    def text(self, text, *, version, dimension):
        return unit_vector(dimension)


class Components:
    def __init__(self, dimension):
        self.dimension = dimension

    def detector(self, selection):
        return Detector()

    def tracker(self, selection):
        return Tracker()

    def image_encoder(self, selection):
        return Encoder(self.dimension)

    def query_gateway(self, selection):
        return Gateway(self.dimension)


class Source:
    def __init__(self, camera_id):
        self.camera_id = camera_id

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return None

    def __iter__(self):
        for index in range(30):
            image = Image.new("RGB", (64, 48))
            yield SourceFrame(self.camera_id, index, index * 40, image, 64, 48)


def active_config(factory):
    with factory() as session:
        config = session.scalar(
            select(AIConfigVersion).where(AIConfigVersion.status == AIConfigStatus.ACTIVE)
        )
        session.expunge(config)
        return config


def counts(factory):
    with factory() as session:
        return {
            model.__tablename__: session.scalar(select(func.count()).select_from(model))
            for model in (PersonTrack, ProcessingJob, StorageOutboxEvent, AuditLog)
        }


def test_diagnostics_never_persist_tracks_jobs_outbox_or_audit(setup):
    config = active_config(setup.factory)
    camera_id = uuid.UUID(setup.camera["id"])
    with setup.factory() as session:
        session.get(Camera, camera_id).rtsp_url = "rtsp://10.0.0.5/stream"
        session.commit()
    runner = ProductionDiagnostics(
        SimpleNamespace(resolve_config=lambda row: SimpleNamespace()),
        Components(config.encoder_dimension),
        lambda camera, cancelled: Source(camera.id),
        settings=DiagnosticSettings(),
    )
    service = MonitoringService(
        lambda: UnitOfWork(setup.factory),
        health=SimpleNamespace(
            check=lambda: SimpleNamespace(components={"postgres": {"status": "ok"}})
        ),
        search=SimpleNamespace(active_config=lambda: active_config(setup.factory)),
        runtime=None,
        diagnostics=runner,
    )
    before = counts(setup.factory)

    pipeline = service.camera_pipeline(camera_id)
    search = service.search_components()

    assert pipeline["overall"] == "SUCCESS"
    assert [step["component"] for step in pipeline["steps"]] == [
        "FRAME_SOURCE",
        "DETECTOR",
        "TRACKER",
        "IMAGE_ENCODER",
    ]
    assert search["overall"] == "SUCCESS"
    assert counts(setup.factory) == before
