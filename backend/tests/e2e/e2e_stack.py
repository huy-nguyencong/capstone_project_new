from __future__ import annotations

import io
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

import sqlalchemy as sa
from dotenv import load_dotenv
from PIL import Image
from sqlalchemy.orm import Session, sessionmaker

from person_search.config import MinioSettings
from person_search.storage.contracts import (
    BoundingBoxPixels,
    EncoderManifest,
    TrackIngestionRequest,
)
from person_search.storage.milvus.client import MilvusStorage
from person_search.storage.milvus.vectors import MilvusPersonTrackIndex
from person_search.storage.minio.client import MinioStorage
from person_search.storage.minio.frames import MinioFrameStore
from person_search.storage.postgres.unit_of_work import UnitOfWork

load_dotenv()

CHECKPOINT = "ab" * 32
FRAME_WIDTH, FRAME_HEIGHT = 96, 64


def unit_vector(index: int, dimension: int = 4) -> list[float]:
    values = [0.0] * dimension
    values[index % dimension] = 1.0
    return values


def jpeg_frame(color: tuple[int, int, int]) -> bytes:
    stream = io.BytesIO()
    Image.new("RGB", (FRAME_WIDTH, FRAME_HEIGHT), color).save(stream, format="JPEG")
    return stream.getvalue()


@contextmanager
def step(name: str, component: str) -> Iterator[None]:
    try:
        yield
    except BaseException as error:
        if isinstance(error, (KeyboardInterrupt, SystemExit)):
            raise
        raise AssertionError(
            f"[{component}] E2E step '{name}' failed: {type(error).__name__}: {error}"
        ) from error


@dataclass
class StorageStack:
    engine: sa.Engine
    session_factory: sessionmaker[Session]
    minio_settings: MinioSettings
    minio: MinioStorage
    milvus: MilvusStorage
    frames: MinioFrameStore
    index: MilvusPersonTrackIndex
    encoder_version: str
    ids: dict[str, uuid.UUID] = field(default_factory=dict)
    timeline_origin: datetime = field(
        default_factory=lambda: datetime.now(UTC).replace(microsecond=0)
    )

    def unit_of_work(self) -> UnitOfWork:
        return UnitOfWork(self.session_factory)

    def encoder(self) -> EncoderManifest:
        return EncoderManifest(
            version=self.encoder_version,
            embedding_dimension=self.index.dimension,
            checkpoint_sha256=CHECKPOINT,
        )

    def request(
        self,
        camera: str,
        *,
        vector: list[float],
        color: tuple[int, int, int] = (0, 128, 0),
        started_at_ms: int = 1_000,
    ) -> TrackIngestionRequest:
        return TrackIngestionRequest(
            track_id=uuid.uuid4(),
            camera_id=self.ids[f"camera_{camera}"],
            area_id=self.ids[f"area_{camera}"],
            processing_job_id=self.ids[f"job_{camera}"],
            ai_config_version_id=self.ids["config"],
            timeline_origin_utc=self.timeline_origin,
            source_frame_index=30,
            source_started_at_ms=started_at_ms,
            representative_frame_timestamp_ms=started_at_ms + 500,
            source_ended_at_ms=started_at_ms + 1_000,
            bbox=BoundingBoxPixels(
                x=10,
                y=8,
                width=24,
                height=48,
                frame_width=FRAME_WIDTH,
                frame_height=FRAME_HEIGHT,
            ),
            frame_bytes=jpeg_frame(color),
            embedding=vector,
            encoder=self.encoder(),
        )

    def execute(self, statement: str, **parameters: Any) -> None:
        with self.engine.begin() as connection:
            connection.execute(sa.text(statement), parameters)


def seed_stack(stack: StorageStack) -> None:
    ids = stack.ids
    for name in (
        "area_a",
        "area_b",
        "camera_a",
        "camera_b",
        "config",
        "job_a",
        "job_b",
        "operator_a",
        "operator_b",
        "viewer",
        "admin",
    ):
        ids[name] = uuid.uuid4()
    suffix = uuid.uuid4().hex[:6].upper()
    for area in ("a", "b"):
        stack.execute(
            "INSERT INTO areas (id, code, name) VALUES (:id, :code, :name)",
            id=ids[f"area_{area}"],
            code=f"E2E-{area.upper()}-{suffix}",
            name=f"E2E Area {area.upper()}",
        )
        stack.execute(
            "INSERT INTO cameras (id, area_id, code, name) VALUES (:id, :area, :code, :name)",
            id=ids[f"camera_{area}"],
            area=ids[f"area_{area}"],
            code=f"E2E-CAM-{area.upper()}-{suffix}",
            name=f"E2E Camera {area.upper()}",
        )
    stack.execute(
        "INSERT INTO ai_config_versions "
        "(id, version, detector_name, detector_version, tracker_name, tracker_version, "
        "encoder_name, encoder_version, encoder_dimension, checkpoint_sha256, status) VALUES "
        "(:id, :version, 'yolo', '1', 'bytetrack', '1', 'rasa', :encoder, :dimension, :sha, "
        "'ACTIVE')",
        id=ids["config"],
        version=f"e2e-{suffix}",
        encoder=stack.encoder_version,
        dimension=stack.index.dimension,
        sha=CHECKPOINT,
    )
    for area in ("a", "b"):
        stack.execute(
            "INSERT INTO processing_jobs (id, camera_id, ai_config_version_id, source_type, "
            "source_ref, sampling_interval, timeline_origin_utc) VALUES "
            "(:id, :camera, :config, 'FILE', 'synthetic.mp4', 10, :origin)",
            id=ids[f"job_{area}"],
            camera=ids[f"camera_{area}"],
            config=ids["config"],
            origin=stack.timeline_origin,
        )
    users = (
        ("operator_a", "OPERATOR", ids["area_a"]),
        ("operator_b", "OPERATOR", ids["area_b"]),
        ("viewer", "VIEWER", None),
        ("admin", "ADMIN", None),
    )
    for name, role, area_id in users:
        stack.execute(
            "INSERT INTO users (id, username, password_hash, display_name, role, "
            "assigned_area_id) VALUES (:id, :username, 'not-a-real-hash', :display, :role, :area)",
            id=ids[name],
            username=f"e2e-{name}-{suffix}".lower(),
            display=name.replace("_", " ").title(),
            role=role,
            area=area_id,
        )
