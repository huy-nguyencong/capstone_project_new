from __future__ import annotations

import os
import uuid
from collections.abc import Iterator

import pytest
import sqlalchemy as sa
from alembic import command
from alembic.config import Config
from e2e_stack import StorageStack, seed_stack
from sqlalchemy.orm import sessionmaker

from person_search.config import MilvusSettings, MinioSettings, PostgresSettings
from person_search.storage.milvus.client import MilvusStorage
from person_search.storage.milvus.vectors import MilvusPersonTrackIndex
from person_search.storage.minio.client import MinioStorage
from person_search.storage.minio.frames import MinioFrameStore


@pytest.fixture
def storage_stack() -> Iterator[StorageStack]:
    if os.getenv("PERSON_SEARCH_RUN_E2E") != "1":
        pytest.skip("set PERSON_SEARCH_RUN_E2E=1 with a disposable database and local stack")
    engine = sa.create_engine(PostgresSettings.from_environment(os.environ).dsn)
    alembic_config = Config("alembic.ini")
    minio_settings = MinioSettings.from_environment(os.environ)
    milvus_settings = MilvusSettings.from_environment(os.environ)
    minio = MinioStorage(minio_settings)
    milvus = MilvusStorage(milvus_settings)
    suffix = uuid.uuid4().hex[:8]
    encoder_version = f"e2e_{suffix}"
    index = MilvusPersonTrackIndex(
        milvus.client,
        encoder_version=encoder_version,
        dimension=4,
        timeout=milvus_settings.timeout_seconds,
        alias=f"person_track_e2e_{suffix}",
    )
    stack = StorageStack(
        engine=engine,
        session_factory=sessionmaker(bind=engine, expire_on_commit=False),
        minio_settings=minio_settings,
        minio=minio,
        milvus=milvus,
        frames=MinioFrameStore(minio.client, minio_settings.bucket),
        index=index,
        encoder_version=encoder_version,
    )
    command.downgrade(alembic_config, "base")
    command.upgrade(alembic_config, "head")
    try:
        index.ensure_collection()
        seed_stack(stack)
        yield stack
    finally:
        try:
            with engine.connect() as connection:
                keys = connection.scalars(
                    sa.text(
                        "SELECT minio_object_key FROM person_tracks "
                        "WHERE minio_object_key IS NOT NULL"
                    )
                ).all()
            for key in keys:
                stack.frames.delete_frame(key)
        finally:
            if milvus.client.has_collection(index.collection_name):
                aliases = milvus.client.list_aliases(index.collection_name).get("aliases", [])
                if index.alias in aliases:
                    milvus.client.drop_alias(index.alias)
                milvus.client.drop_collection(index.collection_name)
            minio.close()
            milvus.close()
            engine.dispose()
            command.downgrade(alembic_config, "base")
