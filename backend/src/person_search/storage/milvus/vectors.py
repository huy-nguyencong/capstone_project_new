"""Versioned Milvus adapter for person-track embeddings."""

from __future__ import annotations

import math
import uuid
from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from pymilvus import DataType, MilvusException

from person_search.storage.contracts import MILVUS_ACTIVE_ALIAS, milvus_collection_name


class InvalidVectorError(ValueError):
    pass


class CollectionContractError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class VectorFilter:
    area_id: uuid.UUID
    camera_id: uuid.UUID | None = None
    appeared_from: datetime | None = None
    appeared_to: datetime | None = None
    camera_ids: tuple[uuid.UUID, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.area_id, uuid.UUID):
            raise ValueError("area_id must be a UUID")
        if self.camera_id is not None and not isinstance(self.camera_id, uuid.UUID):
            raise ValueError("camera_id must be a UUID")
        if not isinstance(self.camera_ids, tuple) or not all(
            isinstance(value, uuid.UUID) for value in self.camera_ids
        ):
            raise ValueError("camera_ids must be a tuple of UUIDs")
        for value in (self.appeared_from, self.appeared_to):
            if value is not None and (value.tzinfo is None or value.utcoffset() is None):
                raise ValueError("time filters must be timezone-aware")
        if (
            self.appeared_from is not None
            and self.appeared_to is not None
            and self.appeared_from > self.appeared_to
        ):
            raise ValueError("appeared_from must not be after appeared_to")

    def expression(self) -> str:
        parts = [f'area_id == "{self.area_id}"', 'index_status == "READY"']
        if self.camera_id is not None:
            parts.append(f'camera_id == "{self.camera_id}"')
        if self.camera_ids:
            quoted = ", ".join(f'"{value}"' for value in self.camera_ids)
            parts.append(f"camera_id in [{quoted}]")
        if self.appeared_from is not None:
            parts.append(f"appeared_at_epoch >= {int(self.appeared_from.timestamp())}")
        if self.appeared_to is not None:
            parts.append(f"appeared_at_epoch <= {int(self.appeared_to.timestamp())}")
        return " and ".join(parts)


MAX_SEARCH_LIMIT = 1024


@dataclass(frozen=True, slots=True)
class VectorSearchHit:
    track_id: uuid.UUID
    score: float


@dataclass(frozen=True, slots=True)
class VectorRecord:
    track_id: uuid.UUID
    vector: Sequence[float]
    area_id: uuid.UUID
    camera_id: uuid.UUID
    appeared_at: datetime


@dataclass(frozen=True, slots=True)
class VectorIndexConfig:
    index_type: str = "HNSW"
    metric_type: str = "IP"
    hnsw_m: int = 16
    ef_construction: int = 128
    search_ef: int = 64


class MilvusPersonTrackIndex:
    def __init__(
        self,
        client: Any,
        *,
        encoder_version: str,
        dimension: int,
        timeout: int = 3,
        alias: str = MILVUS_ACTIVE_ALIAS,
        index_config: VectorIndexConfig | None = None,
    ) -> None:
        self.client = client
        self.encoder_version = encoder_version
        self.dimension = dimension
        self.timeout = timeout
        self.alias = alias
        self.index_config = index_config or VectorIndexConfig()
        self.collection_name = milvus_collection_name(encoder_version)

    def validate_vector(self, vector: Sequence[float]) -> list[float]:
        if len(vector) != self.dimension:
            raise InvalidVectorError(f"Embedding must contain {self.dimension} values.")
        values = [float(value) for value in vector]
        if not all(math.isfinite(value) for value in values):
            raise InvalidVectorError("Embedding values must be finite.")
        norm = math.sqrt(sum(value * value for value in values))
        if not math.isclose(norm, 1.0, abs_tol=1e-3):
            raise InvalidVectorError("Embedding must be L2-normalized.")
        return values

    def ensure_collection(self) -> None:
        if self.client.has_collection(self.collection_name):
            description = self.client.describe_collection(self.collection_name)
            vector_field = next(
                field for field in description["fields"] if field["name"] == "embedding"
            )
            if int(vector_field["params"]["dim"]) != self.dimension:
                raise CollectionContractError("Existing collection has a different dimension.")
        else:
            schema = self.client.create_schema(auto_id=False, enable_dynamic_field=False)
            schema.add_field("track_id", DataType.VARCHAR, is_primary=True, max_length=36)
            schema.add_field("embedding", DataType.FLOAT_VECTOR, dim=self.dimension)
            schema.add_field("area_id", DataType.VARCHAR, max_length=36)
            schema.add_field("camera_id", DataType.VARCHAR, max_length=36)
            schema.add_field("appeared_at_epoch", DataType.INT64)
            schema.add_field("encoder_version", DataType.VARCHAR, max_length=64)
            schema.add_field("index_status", DataType.VARCHAR, max_length=16)
            indexes = self.client.prepare_index_params()
            indexes.add_index(
                field_name="embedding",
                index_type=self.index_config.index_type,
                metric_type=self.index_config.metric_type,
                params={
                    "M": self.index_config.hnsw_m,
                    "efConstruction": self.index_config.ef_construction,
                },
            )
            self.client.create_collection(
                self.collection_name,
                schema=schema,
                index_params=indexes,
                consistency_level="Strong",
                timeout=self.timeout,
            )
        alias_response = self.client.list_aliases(self.collection_name)
        aliases = (
            alias_response.get("aliases", [])
            if isinstance(alias_response, dict)
            else alias_response
        )
        if self.alias not in aliases:
            try:
                current_alias = self.client.describe_alias(self.alias)
            except MilvusException:
                self.client.create_alias(self.collection_name, self.alias)
            else:
                if current_alias["collection_name"] != self.collection_name:
                    self.client.alter_alias(self.collection_name, self.alias)

    def upsert(
        self,
        *,
        track_id: uuid.UUID,
        vector: Sequence[float],
        area_id: uuid.UUID,
        camera_id: uuid.UUID,
        appeared_at: datetime,
    ) -> None:
        self.client.upsert(
            self.collection_name,
            data=self._row(VectorRecord(track_id, vector, area_id, camera_id, appeared_at)),
            timeout=self.timeout,
        )

    def upsert_many(self, records: Sequence[VectorRecord]) -> None:
        """Write many vectors in one request; a restore rebuilds thousands at once."""

        if records:
            self.client.upsert(
                self.collection_name,
                data=[self._row(record) for record in records],
                timeout=self.timeout,
            )

    def _row(self, record: VectorRecord) -> dict[str, Any]:
        return {
            "track_id": str(record.track_id),
            "embedding": self.validate_vector(record.vector),
            "area_id": str(record.area_id),
            "camera_id": str(record.camera_id),
            "appeared_at_epoch": int(record.appeared_at.timestamp()),
            "encoder_version": self.encoder_version,
            "index_status": "READY",
        }

    def existing_ids(self, track_ids: Sequence[uuid.UUID]) -> set[uuid.UUID]:
        """Return which of ``track_ids`` are stored, with one strongly consistent query."""

        if not track_ids:
            return set()
        quoted = ", ".join(f'"{track_id}"' for track_id in track_ids)
        rows = self.client.query(
            self.collection_name,
            filter=f"track_id in [{quoted}]",
            output_fields=["track_id"],
            consistency_level="Strong",
            timeout=self.timeout,
        )
        return {uuid.UUID(row["track_id"]) for row in rows}

    def get(self, track_id: uuid.UUID) -> dict[str, Any] | None:
        rows = self.client.query(
            self.collection_name,
            filter=f'track_id == "{track_id}"',
            output_fields=[
                "track_id",
                "area_id",
                "camera_id",
                "appeared_at_epoch",
                "encoder_version",
                "index_status",
            ],
            consistency_level="Strong",
            timeout=self.timeout,
        )
        return rows[0] if rows else None

    def iter_track_ids(self, *, batch_size: int = 1000) -> Iterator[uuid.UUID]:
        iterator = self.client.query_iterator(
            self.collection_name,
            batch_size=batch_size,
            filter='track_id != ""',
            output_fields=["track_id"],
            consistency_level="Strong",
            timeout=self.timeout,
        )
        try:
            while True:
                rows = iterator.next()
                if not rows:
                    return
                for row in rows:
                    yield uuid.UUID(row["track_id"])
        finally:
            iterator.close()

    def delete(self, track_id: uuid.UUID) -> None:
        self.client.delete(self.collection_name, ids=[str(track_id)], timeout=self.timeout)

    def search(
        self, vector: Sequence[float], filters: VectorFilter, *, top_k: int
    ) -> list[VectorSearchHit]:
        # The service validates the user-facing top_k; larger limits are refill rounds.
        if isinstance(top_k, bool) or not 1 <= top_k <= MAX_SEARCH_LIMIT:
            raise ValueError(f"top_k must be between 1 and {MAX_SEARCH_LIMIT}")
        results = self.client.search(
            self.collection_name,
            data=[self.validate_vector(vector)],
            filter=filters.expression(),
            limit=top_k,
            output_fields=["track_id"],
            search_params={
                "metric_type": self.index_config.metric_type,
                # HNSW requires ef >= limit; a re-ranking pool may ask for more than the default.
                "params": {"ef": max(self.index_config.search_ef, top_k)},
            },
            consistency_level="Strong",
            timeout=self.timeout,
        )
        return [
            VectorSearchHit(uuid.UUID(hit["entity"]["track_id"]), float(hit["distance"]))
            for hit in results[0]
        ]
