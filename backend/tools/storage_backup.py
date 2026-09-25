from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import subprocess
import sys
import time
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import sqlalchemy as sa
from dotenv import load_dotenv
from sqlalchemy.orm import sessionmaker

from person_search.config import StorageSettings
from person_search.services.storage_maintenance import StorageReconciler, StorageReindexer
from person_search.storage.contracts import RASA_EMBEDDING_DIMENSION, RASA_ENCODER_VERSION
from person_search.storage.milvus.client import MilvusStorage
from person_search.storage.milvus.vectors import MilvusPersonTrackIndex
from person_search.storage.minio.client import MinioStorage
from person_search.storage.minio.frames import FrameNotFoundError, MinioFrameStore
from person_search.storage.postgres.unit_of_work import UnitOfWork

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
COMPOSE_FILE = REPOSITORY_ROOT / "infra" / "compose.yaml"
ENVIRONMENT_FILE = REPOSITORY_ROOT / "infra" / ".env"
MANIFEST_VERSION = 1
POSTGRES_DUMP = "postgres.dump"
FRAMES_DIRECTORY = "frames"
FRAMES_INDEX = "frames.json"


class BackupError(RuntimeError):
    pass


def compose(*arguments: str) -> list[str]:
    if not ENVIRONMENT_FILE.exists():
        raise BackupError("infra/.env is missing; copy infra/.env.example and set passwords.")
    return [
        "docker",
        "compose",
        "--env-file",
        str(ENVIRONMENT_FILE),
        "-f",
        str(COMPOSE_FILE),
        *arguments,
    ]


def postgres_shell(script: str) -> list[str]:
    return compose("exec", "-T", "postgres", "sh", "-c", script)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def run_text(command: list[str]) -> str:
    completed = subprocess.run(command, check=True, capture_output=True, text=True)
    return completed.stdout.strip()


def phase(timings: dict[str, float], name: str, started: float) -> None:
    timings[name] = round(time.perf_counter() - started, 3)
    print(f"[{name}] done in {timings[name]}s", file=sys.stderr)


def frame_path(root: Path, object_key: str) -> Path:
    target = (root / FRAMES_DIRECTORY / object_key).resolve()
    if not str(target).startswith(str((root / FRAMES_DIRECTORY).resolve())):
        raise BackupError(f"Refusing unsafe object key: {object_key}")
    return target


def storage_clients() -> tuple[StorageSettings, sa.Engine, MinioStorage, MilvusStorage]:
    load_dotenv()
    settings = StorageSettings.from_environment()
    engine = sa.create_engine(settings.postgres.dsn)
    return settings, engine, MinioStorage(settings.minio), MilvusStorage(settings.milvus)


def backup(output_root: Path) -> Path:
    settings, engine, minio, milvus = storage_clients()
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    target = output_root / stamp
    target.mkdir(parents=True, exist_ok=False)
    timings: dict[str, float] = {}
    try:
        started = time.perf_counter()
        with (target / POSTGRES_DUMP).open("wb") as handle:
            subprocess.run(
                postgres_shell('pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc'),
                check=True,
                stdout=handle,
            )
        pg_dump_version = run_text(postgres_shell("pg_dump --version"))
        alembic_revision = run_text(
            postgres_shell(
                'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -tAc '
                '"SELECT version_num FROM alembic_version"'
            )
        )
        phase(timings, "postgres_dump", started)

        started = time.perf_counter()
        frames = MinioFrameStore(minio.client, settings.minio.bucket)
        with engine.connect() as connection:
            rows = connection.execute(
                sa.text(
                    "SELECT id, minio_object_key, frame_sha256 FROM person_tracks "
                    "WHERE minio_object_key IS NOT NULL ORDER BY id"
                )
            ).all()
            counts = dict(
                connection.execute(
                    sa.text(
                        "SELECT index_status::text, count(*) FROM person_tracks "
                        "GROUP BY index_status"
                    )
                ).all()
            )
        frame_entries = []
        missing = []
        for track_id, object_key, expected_sha in rows:
            try:
                data = frames.get_frame(object_key)
            except FrameNotFoundError:
                missing.append(str(track_id))
                continue
            if hashlib.sha256(data).hexdigest() != expected_sha:
                raise BackupError(f"Frame checksum mismatch for track {track_id}.")
            path = frame_path(target, object_key)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
            frame_entries.append(
                {"track_id": str(track_id), "object_key": object_key, "sha256": expected_sha}
            )
        (target / FRAMES_INDEX).write_text(json.dumps(frame_entries, indent=1) + "\n")
        phase(timings, "frames_export", started)

        files = {
            str(path.relative_to(target)).replace(os.sep, "/"): {
                "sha256": sha256_file(path),
                "bytes": path.stat().st_size,
            }
            for path in sorted(target.rglob("*"))
            if path.is_file()
        }
        manifest = {
            "manifest_version": MANIFEST_VERSION,
            "created_at": datetime.now(UTC).isoformat(),
            "alembic_revision": alembic_revision,
            "pg_dump_version": pg_dump_version,
            "compose_sha256": sha256_file(COMPOSE_FILE),
            "track_counts": counts,
            "frames_exported": len(frame_entries),
            "frames_missing_at_backup": missing,
            "milvus": "not copied; rebuilt from storage_outbox_events.payload by reindex",
            "timings_seconds": timings,
            "files": files,
        }
        (target / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    finally:
        minio.close()
        milvus.close()
        engine.dispose()
    print(json.dumps({"backup": str(target), "timings_seconds": timings}))
    return target


def verify(source: Path) -> dict[str, Any]:
    manifest_path = source / "manifest.json"
    if not manifest_path.exists():
        raise BackupError(f"{manifest_path} does not exist.")
    manifest = json.loads(manifest_path.read_text())
    if manifest.get("manifest_version") != MANIFEST_VERSION:
        raise BackupError("Unsupported backup manifest version.")
    problems = []
    for relative, expected in manifest["files"].items():
        path = source / relative
        if not path.is_file():
            problems.append(f"missing {relative}")
        elif sha256_file(path) != expected["sha256"]:
            problems.append(f"checksum mismatch {relative}")
    if problems:
        raise BackupError("Backup verification failed: " + "; ".join(problems[:10]))
    return manifest


def restore(source: Path, *, confirmed: bool) -> int:
    manifest = verify(source)
    if not confirmed:
        raise BackupError(
            "Restore replaces the PostgreSQL database and re-uploads frames. Re-run with --yes."
        )
    settings, engine, minio, milvus = storage_clients()
    timings: dict[str, float] = {}
    try:
        started = time.perf_counter()
        with (source / POSTGRES_DUMP).open("rb") as handle:
            subprocess.run(
                postgres_shell(
                    'pg_restore -U "$POSTGRES_USER" -d "$POSTGRES_DB" '
                    "--clean --if-exists --no-owner --single-transaction"
                ),
                check=True,
                stdin=handle,
            )
        with engine.connect() as connection:
            revision = connection.scalar(sa.text("SELECT version_num FROM alembic_version"))
        if revision != manifest["alembic_revision"]:
            raise BackupError("Restored alembic revision does not match the manifest.")
        phase(timings, "postgres_restore", started)

        started = time.perf_counter()
        frames = MinioFrameStore(minio.client, settings.minio.bucket)
        restored = skipped = 0
        for entry in json.loads((source / FRAMES_INDEX).read_text()):
            data = frame_path(source, entry["object_key"]).read_bytes()
            if hashlib.sha256(data).hexdigest() != entry["sha256"]:
                raise BackupError(f"Frame file for track {entry['track_id']} is corrupt.")
            try:
                if frames.head_frame(entry["object_key"]).checksum_sha256 == entry["sha256"]:
                    skipped += 1
                    continue
            except FrameNotFoundError:
                pass
            minio.client.put_object(
                settings.minio.bucket,
                entry["object_key"],
                io.BytesIO(data),
                len(data),
                content_type="image/jpeg",
                metadata={"track-id": entry["track_id"], "sha256": entry["sha256"]},
            )
            restored += 1
        phase(timings, "frames_restore", started)

        started = time.perf_counter()
        index = MilvusPersonTrackIndex(
            milvus.client,
            encoder_version=RASA_ENCODER_VERSION,
            dimension=RASA_EMBEDDING_DIMENSION,
            timeout=max(settings.milvus.timeout_seconds, 10),
        )
        index.ensure_collection()
        session_factory = sessionmaker(bind=engine, expire_on_commit=False)

        def unit_of_work() -> UnitOfWork:
            return UnitOfWork(session_factory)

        reindex = StorageReindexer(unit_of_work, index).run()
        phase(timings, "milvus_reindex", started)

        started = time.perf_counter()
        report = StorageReconciler(unit_of_work, frames, index).run()
        phase(timings, "reconcile_dry_run", started)
    finally:
        minio.close()
        milvus.close()
        engine.dispose()

    summary = {
        "restored_from": str(source),
        "frames_uploaded": restored,
        "frames_already_present": skipped,
        "reindex": {"truncated": reindex.truncated, **reindex.counts()},
        "reconciliation": {"clean": report.clean, **report.counts()},
        "timings_seconds": timings,
        "total_seconds": round(sum(timings.values()), 3),
    }
    print(json.dumps(summary, indent=2))
    return 0 if reindex.clean and not (
        report.missing_objects or report.missing_vectors or report.checksum_mismatches
    ) else 2


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Storage backup and restore (STO-19).")
    commands = parser.add_subparsers(dest="command", required=True)
    backup_parser = commands.add_parser("backup")
    backup_parser.add_argument("--output-dir", type=Path, default=REPOSITORY_ROOT / "backups")
    verify_parser = commands.add_parser("verify")
    verify_parser.add_argument("source", type=Path)
    restore_parser = commands.add_parser("restore")
    restore_parser.add_argument("source", type=Path)
    restore_parser.add_argument("--yes", action="store_true")
    arguments = parser.parse_args(argv)
    try:
        if arguments.command == "backup":
            backup(arguments.output_dir)
            return 0
        if arguments.command == "verify":
            manifest = verify(arguments.source)
            print(json.dumps({"verified": str(arguments.source), "files": len(manifest["files"])}))
            return 0
        return restore(arguments.source, confirmed=arguments.yes)
    except (BackupError, subprocess.CalledProcessError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
