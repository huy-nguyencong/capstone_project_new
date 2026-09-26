from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType

import pytest

pytestmark = pytest.mark.unit

TOOLS = Path(__file__).resolve().parents[2] / "tools"


def _load(name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, TOOLS / f"{name}.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


backup_tool = _load("storage_backup")
benchmark_tool = _load("storage_benchmark")


def _write_backup(root: Path) -> Path:
    source = root / "20260925T080000Z"
    (source / "frames" / "tracks" / "v1").mkdir(parents=True)
    (source / "postgres.dump").write_bytes(b"PGDMP-fake")
    (source / "frames" / "tracks" / "v1" / "a.jpg").write_bytes(b"\xff\xd8frame\xff\xd9")
    (source / "frames.json").write_text("[]\n")
    files = {
        str(path.relative_to(source)).replace("\\", "/"): {
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "bytes": path.stat().st_size,
        }
        for path in sorted(source.rglob("*"))
        if path.is_file()
    }
    manifest = {"manifest_version": 1, "alembic_revision": "head", "files": files}
    (source / "manifest.json").write_text(json.dumps(manifest))
    return source


def test_verify_accepts_intact_backup(tmp_path: Path) -> None:
    source = _write_backup(tmp_path)

    manifest = backup_tool.verify(source)

    assert set(manifest["files"]) == {"frames.json", "frames/tracks/v1/a.jpg", "postgres.dump"}


@pytest.mark.parametrize("damage", ["tamper", "delete"])
def test_verify_rejects_damaged_backup(tmp_path: Path, damage: str) -> None:
    source = _write_backup(tmp_path)
    target = source / "postgres.dump"
    if damage == "tamper":
        target.write_bytes(b"PGDMP-changed")
    else:
        target.unlink()

    with pytest.raises(backup_tool.BackupError):
        backup_tool.verify(source)


def test_verify_rejects_unknown_manifest_version(tmp_path: Path) -> None:
    source = _write_backup(tmp_path)
    manifest = json.loads((source / "manifest.json").read_text())
    manifest["manifest_version"] = 99
    (source / "manifest.json").write_text(json.dumps(manifest))

    with pytest.raises(backup_tool.BackupError):
        backup_tool.verify(source)


def test_restore_requires_explicit_confirmation(tmp_path: Path) -> None:
    source = _write_backup(tmp_path)

    with pytest.raises(backup_tool.BackupError, match="--yes"):
        backup_tool.restore(source, confirmed=False)


def test_frame_path_rejects_traversal(tmp_path: Path) -> None:
    assert backup_tool.frame_path(tmp_path, "tracks/v1/x/representative.jpg").is_relative_to(
        tmp_path / "frames"
    )
    with pytest.raises(backup_tool.BackupError):
        backup_tool.frame_path(tmp_path, "../../etc/passwd")


def test_benchmark_percentiles_interpolate() -> None:
    summary = benchmark_tool.latency_summary([10.0, 20.0, 30.0, 40.0])

    assert summary["p50_ms"] == 25.0
    assert summary["p95_ms"] == pytest.approx(38.5)
    assert summary["max_ms"] == 40.0
    assert benchmark_tool.latency_summary([])["count"] == 0


def test_benchmark_vectors_are_unit_length() -> None:
    import random

    vector = benchmark_tool.random_unit_vector(random.Random(1), 256)

    assert len(vector) == 256
    assert sum(value * value for value in vector) == pytest.approx(1.0)


def test_benchmark_codes_satisfy_uppercase_constraint() -> None:
    assert benchmark_tool.benchmark_code("BENCH", "a", "abc123") == "BENCH-A-ABC123"


def test_backup_postgres_command_targets_dsn_database(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(backup_tool, "compose", lambda *arguments: list(arguments))

    command = backup_tool.postgres_command(
        "postgresql+psycopg://app_user:secret@localhost/disposable_db",
        "pg_dump",
        "-Fc",
    )

    assert command == [
        "exec",
        "-T",
        "postgres",
        "pg_dump",
        "-U",
        "app_user",
        "-d",
        "disposable_db",
        "-Fc",
    ]


def test_import_bundle_command_requires_bundle_path_and_config_id() -> None:
    import uuid

    from person_search.storage.maintenance_cli import _parser

    config_id = uuid.uuid4()
    arguments = _parser().parse_args(
        ["import-bundle", "bundle.json", "--config-id", str(config_id)]
    )
    assert arguments.command == "import-bundle"
    assert arguments.path == Path("bundle.json")
    assert arguments.config_id == config_id
    with pytest.raises(SystemExit):
        _parser().parse_args(["import-bundle", "bundle.json"])
