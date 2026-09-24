"""Tests for injectable, lazy storage client wrappers."""

from __future__ import annotations

from contextlib import nullcontext
from typing import Any

import pytest

from person_search.config import MilvusSettings, MinioSettings, PostgresSettings
from person_search.storage.milvus import MilvusStorage
from person_search.storage.minio import MinioStorage
from person_search.storage.postgres import PostgresStorage

pytestmark = pytest.mark.unit


class FakeConnection:
    def __init__(self) -> None:
        self.executed: list[Any] = []

    def execute(self, statement: Any) -> None:
        self.executed.append(statement)


class FakeEngine:
    def __init__(self) -> None:
        self.connection = FakeConnection()
        self.disposed = False

    def connect(self):  # type: ignore[no-untyped-def]
        return nullcontext(self.connection)

    def dispose(self) -> None:
        self.disposed = True


def test_postgres_factory_applies_bounded_pool_and_disposes() -> None:
    engine = FakeEngine()
    received: dict[str, Any] = {}

    def engine_factory(dsn: str, **kwargs: Any):  # type: ignore[no-untyped-def]
        received.update({"dsn": dsn, **kwargs})
        return engine

    settings = PostgresSettings(
        "postgresql+psycopg://user:secret@localhost/database",
        pool_size=3,
        max_overflow=2,
        pool_timeout_seconds=7,
    )
    storage = PostgresStorage.from_settings(settings, engine_factory=engine_factory)  # type: ignore[arg-type]

    storage.check_health()
    storage.close()

    assert received == {
        "dsn": settings.dsn,
        "pool_size": 3,
        "max_overflow": 2,
        "pool_timeout": 7,
        "pool_pre_ping": True,
        "connect_args": {"connect_timeout": 3},
    }
    assert len(engine.connection.executed) == 1
    assert engine.disposed is True


class FakeMilvusClient:
    def __init__(self, **arguments: Any) -> None:
        self.arguments = arguments
        self.closed = False
        self.check_count = 0

    def list_collections(self, **kwargs: Any) -> list[str]:
        self.check_count += 1
        return []

    def close(self) -> None:
        self.closed = True


def test_milvus_client_is_lazy_injectable_and_closable() -> None:
    created: list[FakeMilvusClient] = []

    def factory(**arguments: Any) -> FakeMilvusClient:
        client = FakeMilvusClient(**arguments)
        created.append(client)
        return client

    storage = MilvusStorage(
        MilvusSettings("http://localhost:19530", token="token", database="default"),
        client_factory=factory,
    )

    assert created == []
    storage.check_health()
    storage.check_health()
    storage.close()

    assert len(created) == 1
    assert created[0].arguments == {
        "uri": "http://localhost:19530",
        "db_name": "default",
        "token": "token",
    }
    assert created[0].check_count == 2
    assert created[0].closed is True


class FakeMinioClient:
    def __init__(self, endpoint: str, **arguments: Any) -> None:
        self.endpoint = endpoint
        self.arguments = arguments

    def bucket_exists(self, bucket: str) -> bool:
        return bucket == "person-search-frames"


def test_minio_client_is_lazy_and_checks_required_bucket() -> None:
    created: list[FakeMinioClient] = []

    def factory(endpoint: str, **arguments: Any) -> FakeMinioClient:
        client = FakeMinioClient(endpoint, **arguments)
        created.append(client)
        return client

    storage = MinioStorage(
        MinioSettings("localhost:9000", "access", "secret", "person-search-frames"),
        client_factory=factory,
    )

    assert created == []
    storage.check_health()

    assert len(created) == 1
    assert created[0].endpoint == "localhost:9000"
    assert created[0].arguments["secret_key"] == "secret"


def test_minio_health_fails_when_bucket_is_missing() -> None:
    class MissingBucketClient:
        def bucket_exists(self, bucket: str) -> bool:
            return False

    storage = MinioStorage(
        MinioSettings("localhost:9000", "access", "secret", "missing"),
        client_factory=lambda *args, **kwargs: MissingBucketClient(),
    )

    with pytest.raises(RuntimeError, match="bucket is unavailable"):
        storage.check_health()
