"""Lazy MinIO client wrapper."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from minio import Minio
from urllib3 import PoolManager, Timeout

from person_search.config import MinioSettings


class MinioStorage:
    name = "minio"

    def __init__(
        self,
        settings: MinioSettings,
        *,
        client_factory: Callable[..., Any] = Minio,
    ) -> None:
        self._settings = settings
        self._client_factory = client_factory
        self._client: Any | None = None
        self._http_client: PoolManager | None = None

    @property
    def client(self) -> Any:
        if self._client is None:
            self._http_client = PoolManager(
                timeout=Timeout(
                    connect=self._settings.timeout_seconds,
                    read=self._settings.timeout_seconds,
                ),
                retries=False,
            )
            self._client = self._client_factory(
                self._settings.endpoint,
                access_key=self._settings.access_key,
                secret_key=self._settings.secret_key,
                secure=self._settings.secure,
                http_client=self._http_client,
            )
        return self._client

    def check_health(self) -> None:
        if not self.client.bucket_exists(self._settings.bucket):
            raise RuntimeError("Required application bucket is unavailable.")

    def close(self) -> None:
        self._client = None
        if self._http_client is not None:
            self._http_client.clear()
            self._http_client = None
