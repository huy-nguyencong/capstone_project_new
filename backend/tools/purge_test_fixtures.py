"""Remove integration-test fixtures that were written into the demo database.

Fixtures are recognised only by the exact patterns the integration tests generate:
areas coded ``A-<8 hex>`` and users named ``admin|operator|viewer.<8 hex>``; cameras in those
areas, and jobs/tracks/cases hanging off them, go with them. Seed data, WILDTRACK/RTSP cameras
and real cases are protected: the tool refuses to run if the fixture set touches them.

Dry-run by default; ``--apply`` deletes everything in one transaction. Audit logs are kept:
the append-only trigger is disabled inside that transaction only so the ``ON DELETE SET NULL``
of ``actor_user_id`` can run, then re-enabled before commit (a failure rolls both back).
Afterwards run ``person-search-storage reconcile`` and, after reading
it, ``reconcile --delete-orphans --actor-user-id <admin>`` to drop orphan frames/vectors.
Back up first: ``python tools/storage_backup.py backup``.
"""

from __future__ import annotations

import argparse
import json
import os

import sqlalchemy as sa
from dotenv import load_dotenv

from person_search.config import PostgresSettings

AREA_PATTERN = r"^A-[0-9A-F]{8}$"
USER_PATTERN = r"^(admin|operator|viewer)\.[0-9a-f]{8}$"
PROTECTED_AREAS = ("CAMPUS", "GATE-A")
PROTECTED_USERS = ("admin", "operator", "viewer")

# Temporary id sets, built in dependency order.
SETS = {
    "junk_areas": "SELECT id FROM areas WHERE code ~ :area_pattern",
    "junk_users": "SELECT id FROM users WHERE username ~ :user_pattern",
    "junk_cameras": "SELECT id FROM cameras WHERE area_id IN (SELECT id FROM junk_areas)",
    "junk_jobs": (
        "SELECT id FROM processing_jobs WHERE camera_id IN (SELECT id FROM junk_cameras) "
        "OR requested_by IN (SELECT id FROM junk_users)"
    ),
    "junk_tracks": (
        "SELECT id FROM person_tracks WHERE camera_id IN (SELECT id FROM junk_cameras) "
        "OR processing_job_id IN (SELECT id FROM junk_jobs)"
    ),
    "junk_cases": "SELECT id FROM cases WHERE owner_user_id IN (SELECT id FROM junk_users)",
}

# Each query must return 0 rows, otherwise deleting would touch real data.
SAFETY_CHECKS = {
    "protected area in fixture set": (
        "SELECT code FROM areas WHERE id IN (SELECT id FROM junk_areas) AND code = ANY(:areas)"
    ),
    "protected user in fixture set": (
        "SELECT username FROM users WHERE id IN (SELECT id FROM junk_users) "
        "AND username = ANY(:users)"
    ),
    "real camera in fixture set": (
        "SELECT code FROM cameras WHERE id IN (SELECT id FROM junk_cameras) "
        "AND (code LIKE 'WT-%' OR code LIKE 'RTSP-%' OR code LIKE 'E2E-%')"
    ),
    "fixture job on a real camera": (
        "SELECT id FROM processing_jobs WHERE id IN (SELECT id FROM junk_jobs) "
        "AND camera_id NOT IN (SELECT id FROM junk_cameras)"
    ),
    "real case holding a fixture track": (
        "SELECT case_id FROM case_results WHERE track_id IN (SELECT id FROM junk_tracks) "
        "AND case_id NOT IN (SELECT id FROM junk_cases)"
    ),
    "real user assigned to a fixture area": (
        "SELECT username FROM users WHERE assigned_area_id IN (SELECT id FROM junk_areas) "
        "AND id NOT IN (SELECT id FROM junk_users)"
    ),
}

AUDIT_TRIGGER = "trg_audit_logs_append_only"

# Foreign-key order (all RESTRICT except auth_sessions CASCADE and audit_logs SET NULL).
DELETES = (
    (
        "case_results",
        "DELETE FROM case_results WHERE case_id IN (SELECT id FROM junk_cases) "
        "OR track_id IN (SELECT id FROM junk_tracks)",
    ),
    ("cases", "DELETE FROM cases WHERE id IN (SELECT id FROM junk_cases)"),
    (
        "storage_outbox_events",
        "DELETE FROM storage_outbox_events WHERE track_id IN (SELECT id FROM junk_tracks)",
    ),
    ("person_tracks", "DELETE FROM person_tracks WHERE id IN (SELECT id FROM junk_tracks)"),
    ("processing_jobs", "DELETE FROM processing_jobs WHERE id IN (SELECT id FROM junk_jobs)"),
    ("cameras", "DELETE FROM cameras WHERE id IN (SELECT id FROM junk_cameras)"),
    ("users", "DELETE FROM users WHERE id IN (SELECT id FROM junk_users)"),
    ("areas", "DELETE FROM areas WHERE id IN (SELECT id FROM junk_areas)"),
)

TOTALS = ("areas", "users", "cameras", "processing_jobs", "person_tracks", "cases", "case_results")


def _totals(connection) -> dict[str, int]:
    return {
        table: connection.execute(sa.text(f"SELECT count(*) FROM {table}")).scalar_one()
        for table in TOTALS
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="delete (default: dry-run)")
    args = parser.parse_args()
    load_dotenv()
    engine = sa.create_engine(PostgresSettings.from_environment(os.environ).dsn)
    params = {
        "area_pattern": AREA_PATTERN,
        "user_pattern": USER_PATTERN,
        "areas": list(PROTECTED_AREAS),
        "users": list(PROTECTED_USERS),
    }
    report: dict[str, object] = {"mode": "apply" if args.apply else "dry-run"}
    with engine.begin() as connection:
        report["before"] = _totals(connection)
        for name, query in SETS.items():
            connection.execute(
                sa.text(f"CREATE TEMP TABLE {name} ON COMMIT DROP AS {query}"), params
            )
        report["fixtures"] = {
            name: connection.execute(sa.text(f"SELECT count(*) FROM {name}")).scalar_one()
            for name in SETS
        }
        violations = {}
        for label, query in SAFETY_CHECKS.items():
            rows = [str(row[0]) for row in connection.execute(sa.text(query), params)]
            if rows:
                violations[label] = rows[:5]
        report["safety_violations"] = violations
        if violations:
            print(json.dumps(report, indent=2, ensure_ascii=False))
            print("Refusing to continue: the fixture set touches real data.")
            return 2
        if args.apply:
            report["audit_rows_detached"] = connection.execute(
                sa.text(
                    "SELECT count(*) FROM audit_logs "
                    "WHERE actor_user_id IN (SELECT id FROM junk_users)"
                )
            ).scalar_one()
            connection.execute(sa.text(f"ALTER TABLE audit_logs DISABLE TRIGGER {AUDIT_TRIGGER}"))
            report["deleted"] = {
                table: connection.execute(sa.text(statement)).rowcount
                for table, statement in DELETES
            }
            connection.execute(sa.text(f"ALTER TABLE audit_logs ENABLE TRIGGER {AUDIT_TRIGGER}"))
            report["after"] = _totals(connection)
    engine.dispose()
    print(json.dumps(report, indent=2, ensure_ascii=False))
    if not args.apply:
        print("Dry-run only. Re-run with --apply after reviewing the counts.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
