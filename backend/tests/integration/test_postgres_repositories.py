"""Real PostgreSQL transaction tests for STO-08."""

from __future__ import annotations

import os
import uuid

import pytest
import sqlalchemy as sa
from alembic import command
from alembic.config import Config
from dotenv import load_dotenv
from sqlalchemy.orm import sessionmaker

from person_search.config import PostgresSettings
from person_search.storage.postgres.errors import ConcurrentUpdateError, DuplicateEntityError
from person_search.storage.postgres.models import Area, Case
from person_search.storage.postgres.repositories import CaseRepository
from person_search.storage.postgres.unit_of_work import UnitOfWork

load_dotenv()
pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        os.getenv("PERSON_SEARCH_RUN_MIGRATION_INTEGRATION") != "1",
        reason="set migration integration flag with a disposable database",
    ),
]


def test_unit_of_work_commit_rollback_pagination_and_concurrency() -> None:
    engine = sa.create_engine(PostgresSettings.from_environment(os.environ).dsn)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    config = Config("alembic.ini")
    command.downgrade(config, "base")
    command.upgrade(config, "head")
    try:
        with UnitOfWork(factory) as work:
            assert work.repositories is not None
            work.repositories.areas.add(Area(id=uuid.uuid4(), code="AREA-A", name="Area A"))
            work.repositories.areas.add(Area(id=uuid.uuid4(), code="AREA-B", name="Area B"))
            work.commit()

        with UnitOfWork(factory) as work:
            assert work.repositories is not None
            first_page = work.repositories.areas.page(limit=1)
            second_page = work.repositories.areas.page(limit=1, after_id=first_page[0].id)
            assert len(first_page) == len(second_page) == 1
            assert first_page[0].id < second_page[0].id

        with pytest.raises(RuntimeError):
            with UnitOfWork(factory) as work:
                assert work.repositories is not None
                work.repositories.areas.add(
                    Area(id=uuid.uuid4(), code="ROLLED-BACK", name="Rolled Back")
                )
                raise RuntimeError("service failure")
        with engine.connect() as connection:
            assert (
                connection.scalar(sa.text("SELECT count(*) FROM areas WHERE code = 'ROLLED-BACK'"))
                == 0
            )

        with UnitOfWork(factory) as work:
            assert work.repositories is not None
            work.repositories.areas.add(Area(id=uuid.uuid4(), code="AREA-A", name="Duplicate"))
            with pytest.raises(DuplicateEntityError):
                work.commit()

        with engine.begin() as connection:
            case_id = uuid.uuid4()
            area_id = connection.scalar(sa.text("SELECT id FROM areas ORDER BY id LIMIT 1"))
            operator_id = uuid.uuid4()
            connection.execute(
                sa.text(
                    "INSERT INTO users "
                    "(id, username, password_hash, display_name, role, assigned_area_id) "
                    "VALUES (:id, 'operator-repo', 'hash', 'Operator', 'OPERATOR', :area)"
                ),
                {"id": operator_id, "area": area_id},
            )
            connection.execute(
                sa.text(
                    "INSERT INTO cases (id, owner_user_id, title) VALUES (:id, :owner, 'Original')"
                ),
                {"id": case_id, "owner": operator_id},
            )
        session_a, session_b = factory(), factory()
        try:
            case_a = session_a.get(Case, case_id)
            case_b = session_b.get(Case, case_id)
            assert case_a is not None and case_b is not None

            CaseRepository(session_a).rename_if_unchanged(
                case_id, title="Writer A", expected_updated_at=case_a.updated_at
            )
            session_a.commit()
            with pytest.raises(ConcurrentUpdateError):
                CaseRepository(session_b).rename_if_unchanged(
                    case_id, title="Writer B", expected_updated_at=case_b.updated_at
                )
        finally:
            session_a.close()
            session_b.close()
    finally:
        engine.dispose()
        command.downgrade(config, "base")
