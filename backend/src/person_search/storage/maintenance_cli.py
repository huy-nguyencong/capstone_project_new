from __future__ import annotations

import argparse
import json
import logging
import uuid
from collections.abc import Sequence
from dataclasses import asdict
from datetime import timedelta
from pathlib import Path

from dotenv import load_dotenv

from person_search.config import StorageSettings
from person_search.services.storage_maintenance import (
    OutboxRetryWorker,
    StorageReconciler,
    StorageReindexer,
)
from person_search.services.track_ingestion import TrackIngestionService
from person_search.storage.contracts import (
    MILVUS_ACTIVE_ALIAS,
    RASA_EMBEDDING_DIMENSION,
    RASA_ENCODER_VERSION,
)
from person_search.storage.milvus.vectors import MilvusPersonTrackIndex
from person_search.storage.minio.frames import MinioFrameStore
from person_search.storage.postgres.unit_of_work import UnitOfWork
from person_search.storage.runtime import StorageRuntime


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="person-search-storage")
    parser.add_argument("--encoder-version", default=RASA_ENCODER_VERSION)
    parser.add_argument("--dimension", type=int, default=RASA_EMBEDDING_DIMENSION)
    parser.add_argument("--alias", default=MILVUS_ACTIVE_ALIAS)
    commands = parser.add_subparsers(dest="command", required=True)
    retry = commands.add_parser("retry-outbox", help="Resume due track ingestion events.")
    retry.add_argument("--limit", type=int, default=50)
    reconcile = commands.add_parser(
        "reconcile", help="Cross-check PostgreSQL, MinIO and Milvus (dry-run by default)."
    )
    reconcile.add_argument("--delete-orphans", action="store_true")
    reconcile.add_argument("--quarantine-corrupt", action="store_true")
    reconcile.add_argument("--stale-minutes", type=int, default=30)
    reconcile.add_argument("--max-items", type=int, default=10_000)
    reconcile.add_argument("--actor-user-id", type=uuid.UUID)
    reindex = commands.add_parser(
        "reindex", help="Rebuild Milvus vectors of READY tracks from PostgreSQL outbox payloads."
    )
    reindex.add_argument("--no-verify", action="store_true")
    reindex.add_argument("--max-items", type=int, default=100_000)
    requeue = commands.add_parser("requeue-track", help="Move one FAILED track back to PENDING.")
    requeue.add_argument("track_id", type=uuid.UUID)
    requeue.add_argument("--actor-user-id", type=uuid.UUID)
    bundle = commands.add_parser(
        "import-bundle",
        help="Verify a batch result bundle and publish it through the ingestion invariant.",
    )
    bundle.add_argument("path", type=Path)
    bundle.add_argument("--config-id", type=uuid.UUID, required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    arguments = _parser().parse_args(argv)
    load_dotenv()
    logging.basicConfig(level=logging.INFO)
    settings = StorageSettings.from_environment()
    runtime = StorageRuntime.from_settings(settings)
    try:
        frames = MinioFrameStore(runtime.minio.client, settings.minio.bucket)
        vectors = MilvusPersonTrackIndex(
            runtime.milvus.client,
            encoder_version=arguments.encoder_version,
            dimension=arguments.dimension,
            timeout=settings.milvus.timeout_seconds,
            alias=arguments.alias,
        )

        def unit_of_work() -> UnitOfWork:
            return UnitOfWork(runtime.postgres.session_factory)

        if arguments.command == "import-bundle":
            return _import_bundle(arguments, runtime, settings, frames, unit_of_work)
        ingestion = TrackIngestionService(unit_of_work, frames, vectors)
        if arguments.command == "retry-outbox":
            summary = OutboxRetryWorker(unit_of_work, ingestion).run_once(limit=arguments.limit)
            print(json.dumps(asdict(summary)))
            return 0 if summary.errors == 0 else 1
        if arguments.command == "reconcile":
            report = StorageReconciler(
                unit_of_work,
                frames,
                vectors,
                stale_after=timedelta(minutes=arguments.stale_minutes),
                max_items=arguments.max_items,
            ).run(
                delete_orphans=arguments.delete_orphans,
                quarantine_corrupt=arguments.quarantine_corrupt,
                actor_user_id=arguments.actor_user_id,
            )
            print(
                json.dumps(
                    {"dry_run": report.dry_run, "truncated": report.truncated, **report.counts()}
                )
            )
            return 0 if report.clean else 2
        if arguments.command == "reindex":
            vectors.ensure_collection()
            rebuilt = StorageReindexer(
                unit_of_work,
                vectors,
                max_items=arguments.max_items,
                verify=not arguments.no_verify,
            ).run()
            print(json.dumps({"truncated": rebuilt.truncated, **rebuilt.counts()}))
            return 0 if rebuilt.clean else 2
        result = ingestion.requeue_failed(arguments.track_id, actor_user_id=arguments.actor_user_id)
        print(json.dumps({"track_id": str(result.track_id), "status": result.status.value}))
        return 0
    finally:
        runtime.close()


def _import_bundle(arguments, runtime, settings, frames, unit_of_work) -> int:
    from person_search.storage.contracts import EncoderManifest
    from person_search.storage.postgres.models import AIConfigVersion
    from person_search.workers.publication import BundleImporter

    with unit_of_work() as work:
        config = work.session.get(AIConfigVersion, arguments.config_id)
        if config is None:
            print(json.dumps({"error": "ai_config_not_found"}))
            return 2
        manifest = EncoderManifest(
            version=config.encoder_version,
            embedding_dimension=config.encoder_dimension,
            checkpoint_sha256=config.checkpoint_sha256,
        )
    vectors = MilvusPersonTrackIndex(
        runtime.milvus.client,
        encoder_version=manifest.version,
        dimension=manifest.embedding_dimension,
        timeout=settings.milvus.timeout_seconds,
        alias=arguments.alias,
    )
    vectors.ensure_collection()
    ingestion = TrackIngestionService(unit_of_work, frames, vectors)
    ready = BundleImporter(ingestion, arguments.config_id, manifest).import_file(arguments.path)
    print(json.dumps({"imported_ready_tracks": ready}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
