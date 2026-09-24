"""Lazy Milvus client wrapper."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from pymilvus import MilvusClient

from person_search.config import MilvusSettings


class MilvusStorage:
    name = "milvus"

    def __init__(
        self,
        settings: MilvusSettings,
        *,
        client_factory: Callable[..., Any] = MilvusClient,
    ) -> None:
        self._settings = settings
        self._client_factory = client_factory
        self._client: Any | None = None

    @property
    def client(self) -> Any:
        if self._client is None:
            arguments: dict[str, Any] = {
                "uri": self._settings.uri,
                "db_name": self._settings.database,
            }
            if self._settings.token:
                arguments["token"] = self._settings.token
            self._client = self._client_factory(**arguments)
        return self._client

    def check_health(self) -> None:
        self.client.list_collections(timeout=self._settings.timeout_seconds)

    def close(self) -> None:
        if self._client is not None:
            self._client.close()
            self._client = None
