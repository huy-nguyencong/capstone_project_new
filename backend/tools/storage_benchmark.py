from __future__ import annotations

import argparse
import io
import json
import math
import os
import platform
import random
import statistics
import subprocess
import sys
import time
import uuid
from collections.abc import Callable, Sequence
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import sqlalchemy as sa
from dotenv import load_dotenv
from PIL import Image
from sqlalchemy.orm import sessionmaker

from person_search.config import StorageSettings
from person_search.services.track_imagery import ImageVariant, TrackImageService
from person_search.services.track_ingestion import TrackIngestionService
from person_search.services.track_search import TrackSearchQuery, TrackSearchService
from person_search.storage.contracts import (
    BoundingBoxPixels,
    EncoderManifest,
    TrackIngestionRequest,
)
from person_search.storage.milvus.client import MilvusStorage
from person_search.storage.milvus.vectors import (
    MilvusPersonTrackIndex,
    VectorFilter,
    VectorIndexConfig,
)
from person_search.storage.minio.client import MinioStorage
from person_search.storage.minio.frames import MinioFrameStore
from person_search.storage.postgres.models import TrackIndexStatus
from person_search.storage.postgres.unit_of_work import UnitOfWork

CHECKPOINT = "be" * 32
CAMERAS = (("A", 4), ("B", 3))
FRAME_VARIANTS = 8


def benchmark_code(*parts: str) -> str:
    """Build identifiers that satisfy the uppercase database constraint."""
    return "-".join(parts).upper()


def percentile(values: Sequence[float], fraction: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    position = (len(ordered) - 1) * fraction
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (position - lower)


def latency_summary(values: Sequence[float]) -> dict[str, float]:
    return {
        "count": len(values),
        "mean_ms": round(statistics.fmean(values), 3) if values else 0.0,
        "p50_ms": round(percentile(values, 0.50), 3),
        "p95_ms": round(percentile(values, 0.95), 3),
        "p99_ms": round(percentile(values, 0.99), 3),
        "max_ms": round(max(values), 3) if values else 0.0,
    }


def random_unit_vector(rng: random.Random, dimension: int) -> list[float]:
    values = [rng.gauss(0.0, 1.0) for _ in range(dimension)]
    norm = math.sqrt(sum(value * value for value in values)) or 1.0
    return [value / norm for value in values]


def noise_jpeg(rng: random.Random, width: int, height: int, quality: int) -> bytes:
    small = (max(2, width // 16), max(2, height // 16))
    image = Image.frombytes("RGB", small, rng.randbytes(small[0] * small[1] * 3))
    image = image.resize((width, height), Image.Resampling.BICUBIC)
    stream = io.BytesIO()
    image.save(stream, format="JPEG", quality=quality)
    return stream.getvalue()


def timed(action: Callable[[], Any]) -> tuple[float, Any]:
    started = time.perf_counter()
    result = action()
    return (time.perf_counter() - started) * 1000, result


def machine_info() -> dict[str, Any]:
    info: dict[str, Any] = {
        "platform": platform.platform(),
        "processor": platform.processor() or platform.machine(),
        "cpu_count": os.cpu_count(),
        "python": sys.version.split()[0],
    }
    try:
        info["memory_bytes"] = os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES")
    except (AttributeError, ValueError, OSError):
        info["memory_bytes"] = None
    return info


def docker_stats(project: str) -> list[dict[str, str]]:
    try:
        completed = subprocess.run(
            ["docker", "stats", "--no-stream", "--format", "{{json .}}"],
            check=True,
            capture_output=True,
            text=True,
            timeout=60,
        )
    except (OSError, subprocess.SubprocessError) as error:
        return [{"error": type(error).__name__}]
    rows = []
    for line in completed.stdout.splitlines():
        row = json.loads(line)
        if project in row.get("Name", ""):
            rows.append(
                {
                    "name": row.get("Name", ""),
                    "cpu": row.get("CPUPerc", ""),
                    "memory": row.get("MemUsage", ""),
                    "memory_percent": row.get("MemPerc", ""),
                    "block_io": row.get("BlockIO", ""),
                }
            )
    return rows


@dataclass
class Fixture:
    suffix: str
    ids: dict[str, uuid.UUID] = field(default_factory=dict)
    camera_areas: dict[uuid.UUID, uuid.UUID] = field(default_factory=dict)
    origin: datetime = field(
        default_factory=lambda: datetime.now(UTC).replace(microsecond=0) - timedelta(days=1)
    )


def seed(engine: sa.Engine, fixture: Fixture, encoder_version: str, dimension: int) -> None:
    ids = fixture.ids
    with engine.begin() as connection:
        def execute(statement: str, **parameters: Any) -> None:
            connection.execute(sa.text(statement), parameters)

        ids["config"] = uuid.uuid4()
        execute(
            "INSERT INTO ai_config_versions (id, version, detector_name, detector_version, "
            "tracker_name, tracker_version, encoder_name, encoder_version, encoder_dimension, "
            "checkpoint_sha256, status) VALUES (:id, :version, 'bench', '1', 'bench', '1', "
            "'bench', :encoder, :dimension, :sha, 'DRAFT')",
            id=ids["config"],
            version=f"bench-{fixture.suffix}",
            encoder=encoder_version,
            dimension=dimension,
            sha=CHECKPOINT,
        )
        for area_name, camera_count in CAMERAS:
            area_id = uuid.uuid4()
            ids[f"area_{area_name}"] = area_id
            execute(
                "INSERT INTO areas (id, code, name) VALUES (:id, :code, :name)",
                id=area_id,
                code=benchmark_code("BENCH", area_name, fixture.suffix),
                name=f"Bench {area_name}",
            )
            for index in range(camera_count):
                camera_id, job_id = uuid.uuid4(), uuid.uuid4()
                fixture.camera_areas[camera_id] = area_id
                ids[f"job_{camera_id}"] = job_id
                execute(
                    "INSERT INTO cameras (id, area_id, code, name) VALUES "
                    "(:id, :area, :code, :name)",
                    id=camera_id,
                    area=area_id,
                    code=benchmark_code("BENCH", f"{area_name}{index}", fixture.suffix),
                    name=f"Bench camera {area_name}{index}",
                )
                execute(
                    "INSERT INTO processing_jobs (id, camera_id, ai_config_version_id, "
                    "source_type, source_ref, sampling_interval, timeline_origin_utc) VALUES "
                    "(:id, :camera, :config, 'FILE', 'synthetic.mp4', 10, :origin)",
                    id=job_id,
                    camera=camera_id,
                    config=ids["config"],
                    origin=fixture.origin,
                )
        ids["operator"] = uuid.uuid4()
        execute(
            "INSERT INTO users (id, username, password_hash, display_name, role, "
            "assigned_area_id) VALUES (:id, :username, 'benchmark-no-login', 'Bench', "
            "'OPERATOR', :area)",
            id=ids["operator"],
            username=f"bench-{fixture.suffix}",
            area=ids["area_A"],
        )


def cleanup(engine: sa.Engine, fixture: Fixture) -> None:
    cameras = list(fixture.camera_areas)
    with engine.begin() as connection:
        def execute(statement: str, **parameters: Any) -> None:
            connection.execute(sa.text(statement), parameters)

        execute(
            "DELETE FROM storage_outbox_events WHERE track_id IN "
            "(SELECT id FROM person_tracks WHERE camera_id = ANY(:cameras))",
            cameras=cameras,
        )
        execute("DELETE FROM person_tracks WHERE camera_id = ANY(:cameras)", cameras=cameras)
        execute("DELETE FROM processing_jobs WHERE camera_id = ANY(:cameras)", cameras=cameras)
        execute("DELETE FROM users WHERE id = :id", id=fixture.ids.get("operator"))
        execute("DELETE FROM cameras WHERE id = ANY(:cameras)", cameras=cameras)
        execute("DELETE FROM ai_config_versions WHERE id = :id", id=fixture.ids.get("config"))
        execute(
            "DELETE FROM areas WHERE id = ANY(:areas)",
            areas=[value for key, value in fixture.ids.items() if key.startswith("area_")],
        )


def parse_frame_size(value: str) -> tuple[int, int]:
    width, height = value.lower().split("x")
    return int(width), int(height)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Synthetic storage benchmark (STO-18).")
    parser.add_argument("--tracks", type=int, default=500)
    parser.add_argument("--queries", type=int, default=100)
    parser.add_argument("--images", type=int, default=50)
    parser.add_argument("--dimension", type=int, default=256)
    parser.add_argument("--frame-size", type=parse_frame_size, default=(1280, 720))
    parser.add_argument("--jpeg-quality", type=int, default=85)
    parser.add_argument("--ingest-concurrency", type=int, default=1)
    parser.add_argument("--search-concurrency", type=int, default=1)
    parser.add_argument("--top-k", type=int, default=16, choices=(4, 8, 12, 16))
    parser.add_argument("--ef", default="32,64,128")
    parser.add_argument("--seed", type=int, default=20260925)
    parser.add_argument("--tracks-per-video", type=int)
    parser.add_argument("--videos", type=int, default=7)
    parser.add_argument("--docker-stats", action="store_true")
    parser.add_argument("--compose-project", default="person-search-storage")
    parser.add_argument("--keep-data", action="store_true")
    parser.add_argument("--output", type=Path)
    arguments = parser.parse_args(argv)

    load_dotenv()
    settings = StorageSettings.from_environment()
    rng = random.Random(arguments.seed)
    width, height = arguments.frame_size
    suffix = uuid.uuid4().hex[:8]
    encoder_version = f"bench_{suffix}"
    report: dict[str, Any] = {
        "generated_at": datetime.now(UTC).isoformat(),
        "machine": machine_info(),
        "parameters": {
            key: str(value) if isinstance(value, Path) else value
            for key, value in vars(arguments).items()
        },
    }
    if arguments.docker_stats:
        report["docker_idle"] = docker_stats(arguments.compose_project)

    engine = sa.create_engine(
        settings.postgres.dsn,
        pool_size=max(5, arguments.ingest_concurrency, arguments.search_concurrency) + 2,
    )
    session_factory = sessionmaker(bind=engine, expire_on_commit=False)
    minio = MinioStorage(settings.minio)
    milvus = MilvusStorage(settings.milvus)
    frames = MinioFrameStore(minio.client, settings.minio.bucket)
    index = MilvusPersonTrackIndex(
        milvus.client,
        encoder_version=encoder_version,
        dimension=arguments.dimension,
        timeout=max(settings.milvus.timeout_seconds, 10),
        alias=f"person_track_bench_{suffix}",
    )
    fixture = Fixture(suffix)
    frame_keys: list[str] = []

    def unit_of_work() -> UnitOfWork:
        return UnitOfWork(session_factory)

    try:
        index.ensure_collection()
        seed(engine, fixture, encoder_version, arguments.dimension)
        manifest = EncoderManifest(
            version=encoder_version,
            embedding_dimension=arguments.dimension,
            checkpoint_sha256=CHECKPOINT,
        )
        frame_pool = [
            noise_jpeg(rng, width, height, arguments.jpeg_quality) for _ in range(FRAME_VARIANTS)
        ]
        cameras = list(fixture.camera_areas)
        requests = []
        vectors_by_area: dict[uuid.UUID, dict[uuid.UUID, list[float]]] = {}
        for number in range(arguments.tracks):
            camera_id = cameras[number % len(cameras)]
            vector = random_unit_vector(rng, arguments.dimension)
            started_ms = rng.randrange(0, 20 * 3600 * 1000)
            box_width = rng.randrange(max(8, width // 20), max(9, width // 6))
            box_height = rng.randrange(max(16, height // 6), max(17, height // 2))
            request = TrackIngestionRequest(
                track_id=uuid.uuid4(),
                camera_id=camera_id,
                area_id=fixture.camera_areas[camera_id],
                processing_job_id=fixture.ids[f"job_{camera_id}"],
                ai_config_version_id=fixture.ids["config"],
                timeline_origin_utc=fixture.origin,
                source_frame_index=started_ms // 100,
                source_started_at_ms=started_ms,
                representative_frame_timestamp_ms=started_ms + 500,
                source_ended_at_ms=started_ms + 2_000,
                bbox=BoundingBoxPixels(
                    x=rng.randrange(0, width - box_width),
                    y=rng.randrange(0, height - box_height),
                    width=box_width,
                    height=box_height,
                    frame_width=width,
                    frame_height=height,
                ),
                frame_bytes=frame_pool[number % FRAME_VARIANTS],
                embedding=vector,
                encoder=manifest,
            )
            requests.append(request)
            vectors_by_area.setdefault(request.area_id, {})[request.track_id] = vector

        ingestion = TrackIngestionService(unit_of_work, frames, index)
        ingest_latencies: list[float] = []
        statuses: dict[str, int] = {}
        started = time.perf_counter()
        with ThreadPoolExecutor(max_workers=arguments.ingest_concurrency) as pool:
            for elapsed, result in pool.map(
                lambda item: timed(lambda: ingestion.ingest_track(item)), requests
            ):
                ingest_latencies.append(elapsed)
                statuses[result.status.value] = statuses.get(result.status.value, 0) + 1
        ingest_seconds = time.perf_counter() - started
        report["ingestion"] = {
            "tracks": len(requests),
            "statuses": statuses,
            "seconds": round(ingest_seconds, 3),
            "tracks_per_second": round(len(requests) / ingest_seconds, 3),
            "latency": latency_summary(ingest_latencies),
        }
        with engine.connect() as connection:
            frame_keys = list(
                connection.scalars(
                    sa.text(
                        "SELECT minio_object_key FROM person_tracks WHERE camera_id = ANY(:c) "
                        "AND minio_object_key IS NOT NULL"
                    ),
                    {"c": cameras},
                )
            )
        if arguments.docker_stats:
            report["docker_after_ingest"] = docker_stats(arguments.compose_project)

        area_a = fixture.ids["area_A"]
        area_vectors = vectors_by_area.get(area_a, {})
        queries = [
            random_unit_vector(rng, arguments.dimension) for _ in range(arguments.queries)
        ]
        search_results: dict[str, Any] = {}
        for ef in [int(value) for value in arguments.ef.split(",") if value]:
            variant = MilvusPersonTrackIndex(
                milvus.client,
                encoder_version=encoder_version,
                dimension=arguments.dimension,
                timeout=max(settings.milvus.timeout_seconds, 10),
                alias=index.alias,
                index_config=VectorIndexConfig(search_ef=max(ef, arguments.top_k)),
            )
            service = TrackSearchService(unit_of_work, variant)
            milvus_latencies: list[float] = []
            service_latencies: list[float] = []
            recalls: list[float] = []

            def run_query(vector: list[float], variant: Any = variant, service: Any = service):
                raw_ms, hits = timed(
                    lambda: variant.search(
                        vector, VectorFilter(area_id=area_a), top_k=arguments.top_k
                    )
                )
                full_ms, _ = timed(
                    lambda: service.search(
                        fixture.ids["operator"], TrackSearchQuery(vector, top_k=arguments.top_k)
                    )
                )
                exact = sorted(
                    area_vectors,
                    key=lambda track_id: -sum(
                        a * b for a, b in zip(vector, area_vectors[track_id], strict=True)
                    ),
                )[: arguments.top_k]
                found = {hit.track_id for hit in hits}
                recall = len(found & set(exact)) / len(exact) if exact else 1.0
                return raw_ms, full_ms, recall

            with ThreadPoolExecutor(max_workers=arguments.search_concurrency) as pool:
                for raw_ms, full_ms, recall in pool.map(run_query, queries):
                    milvus_latencies.append(raw_ms)
                    service_latencies.append(full_ms)
                    recalls.append(recall)
            search_results[str(ef)] = {
                "milvus_search": latency_summary(milvus_latencies),
                "service_search_with_hydrate": latency_summary(service_latencies),
                "recall_at_k_mean": round(statistics.fmean(recalls), 4) if recalls else None,
                "recall_at_k_min": round(min(recalls), 4) if recalls else None,
            }
        report["search"] = {
            "top_k": arguments.top_k,
            "area_tracks": len(area_vectors),
            "by_ef": search_results,
        }

        imagery = TrackImageService(unit_of_work, frames)
        ready_in_area = list(area_vectors)[: arguments.images]
        crop_latencies = [
            timed(
                lambda track_id=track_id: imagery.search_result_image(
                    fixture.ids["operator"], track_id, ImageVariant.PERSON_CROP
                )
            )[0]
            for track_id in ready_in_area
        ]
        frame_latencies = [
            timed(
                lambda track_id=track_id: imagery.search_result_image(
                    fixture.ids["operator"], track_id, ImageVariant.FULL_FRAME
                )
            )[0]
            for track_id in ready_in_area
        ]
        report["imagery"] = {
            "person_crop": latency_summary(crop_latencies),
            "full_frame": latency_summary(frame_latencies),
        }

        with engine.connect() as connection:
            row = connection.execute(
                sa.text(
                    "SELECT count(*), avg(frame_size_bytes), "
                    "avg(pg_column_size(t.*)), "
                    "(SELECT avg(pg_column_size(o.payload)) FROM storage_outbox_events o "
                    " JOIN person_tracks p ON p.id = o.track_id WHERE p.camera_id = ANY(:c)) "
                    "FROM person_tracks t WHERE t.camera_id = ANY(:c)"
                ),
                {"c": cameras},
            ).one()
            table_sizes = {
                name: connection.scalar(sa.text(f"SELECT pg_total_relation_size('{name}')"))
                for name in ("person_tracks", "storage_outbox_events", "case_results")
            }
        ready = statuses.get(TrackIndexStatus.READY.value, 0)
        frame_bytes = float(row[1] or 0)
        track_row_bytes = float(row[2] or 0)
        outbox_bytes = float(row[3] or 0)
        vector_bytes = arguments.dimension * 4
        per_track = frame_bytes + track_row_bytes + outbox_bytes + vector_bytes
        report["storage"] = {
            "tracks_measured": int(row[0]),
            "avg_frame_bytes": round(frame_bytes),
            "avg_track_row_bytes": round(track_row_bytes),
            "avg_outbox_payload_bytes": round(outbox_bytes),
            "raw_vector_bytes": vector_bytes,
            "estimated_bytes_per_track_excluding_indexes": round(per_track),
            "postgres_table_total_bytes": table_sizes,
            "milvus_collection_stats": milvus.client.get_collection_stats(index.collection_name),
        }
        if arguments.tracks_per_video:
            projected_tracks = arguments.tracks_per_video * arguments.videos
            report["capacity_projection"] = {
                "videos": arguments.videos,
                "tracks_per_video": arguments.tracks_per_video,
                "projected_tracks": projected_tracks,
                "projected_bytes_excluding_indexes": round(projected_tracks * per_track),
            }
        report["ready_tracks"] = ready
    finally:
        if not arguments.keep_data:
            for key in frame_keys:
                try:
                    frames.delete_frame(key)
                except Exception:
                    pass
            try:
                if milvus.client.has_collection(index.collection_name):
                    aliases = milvus.client.list_aliases(index.collection_name).get("aliases", [])
                    if index.alias in aliases:
                        milvus.client.drop_alias(index.alias)
                    milvus.client.drop_collection(index.collection_name)
            finally:
                if fixture.ids:
                    cleanup(engine, fixture)
        minio.close()
        milvus.close()
        engine.dispose()

    text = json.dumps(report, indent=2, default=str)
    if arguments.output:
        arguments.output.parent.mkdir(parents=True, exist_ok=True)
        arguments.output.write_text(text + "\n")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
