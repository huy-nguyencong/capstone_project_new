"""Lifecycle owner for the three storage clients."""

from __future__ import annotations

from dataclasses import dataclass

from person_search.config import StorageSettings
from person_search.storage.health import StorageHealthService
from person_search.storage.milvus.client import MilvusStorage
from person_search.storage.minio.client import MinioStorage
from person_search.storage.postgres.client import PostgresStorage


@dataclass(slots=True)
class StorageRuntime:
    settings: StorageSettings
    postgres: PostgresStorage
    milvus: MilvusStorage
    minio: MinioStorage
    health: StorageHealthService
    _closed: bool = False

    @classmethod
    def from_settings(cls, settings: StorageSettings) -> StorageRuntime:
        postgres = PostgresStorage.from_settings(settings.postgres)
        milvus = MilvusStorage(settings.milvus)
        minio = MinioStorage(settings.minio)
        health = StorageHealthService(
            (postgres, milvus, minio), secrets=settings.secret_values()
        )
        return cls(settings, postgres, milvus, minio, health)

    def close(self) -> None:
        if self._closed:
            return
        self.minio.close()
        self.milvus.close()
        self.postgres.close()
        self._closed = True
