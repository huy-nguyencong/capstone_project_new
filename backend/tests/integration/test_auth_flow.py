from __future__ import annotations

import os
import uuid

import pytest
import sqlalchemy as sa
from alembic import command
from alembic.config import Config
from dotenv import load_dotenv
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from person_search import create_app
from person_search.auth.cli import CommandError, create_user, set_password
from person_search.auth.passwords import PasswordHasher
from person_search.config import PostgresSettings
from person_search.dependencies import DependencyContainer
from person_search.services.auth import AuthService
from person_search.storage.postgres.models import UserRole
from person_search.storage.postgres.unit_of_work import UnitOfWork

load_dotenv()
pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        os.getenv("PERSON_SEARCH_RUN_MIGRATION_INTEGRATION") != "1",
        reason="set PERSON_SEARCH_RUN_MIGRATION_INTEGRATION=1 with a disposable database",
    ),
]

PASSWORD = "integration-password"


def test_cli_accounts_login_session_and_logout_against_postgres() -> None:
    engine = sa.create_engine(PostgresSettings.from_environment(os.environ).dsn)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    config = Config("alembic.ini")
    hasher = PasswordHasher(time_cost=1, memory_cost=1024, parallelism=1)

    def unit_of_work() -> UnitOfWork:
        return UnitOfWork(factory)

    command.downgrade(config, "base")
    command.upgrade(config, "head")
    try:
        command.check(config)
        with engine.begin() as connection:
            connection.execute(
                sa.text("INSERT INTO areas (id, code, name) VALUES (:id, 'GATE-A', 'Gate A')"),
                {"id": uuid.uuid4()},
            )
        create_user(
            unit_of_work,
            hasher,
            username="Admin",
            display_name="Admin",
            role=UserRole.ADMIN,
            password=PASSWORD,
            area_code=None,
        )
        create_user(
            unit_of_work,
            hasher,
            username="khoa.tran",
            display_name="Khoa",
            role=UserRole.OPERATOR,
            password=PASSWORD,
            area_code="GATE-A",
        )
        with pytest.raises(CommandError, match="already exists"):
            create_user(
                unit_of_work,
                hasher,
                username="ADMIN",
                display_name="Dup",
                role=UserRole.ADMIN,
                password=PASSWORD,
                area_code=None,
            )
        with pytest.raises(CommandError, match="does not exist"):
            create_user(
                unit_of_work,
                hasher,
                username="ghost",
                display_name="Ghost",
                role=UserRole.OPERATOR,
                password=PASSWORD,
                area_code="NOPE",
            )
        set_password(unit_of_work, hasher, username="khoa.tran", password=PASSWORD + "-2")

        container = DependencyContainer()
        container.register("auth.service", AuthService(unit_of_work, hasher=hasher))
        client = create_app({"TESTING": True}, dependencies=container).test_client()

        assert (
            client.post(
                "/api/v1/auth/login", json={"username": "khoa.tran", "password": PASSWORD}
            ).status_code
            == 401
        )
        login = client.post(
            "/api/v1/auth/login", json={"username": "KHOA.TRAN", "password": PASSWORD + "-2"}
        )
        assert login.status_code == 200
        assert login.get_json()["user"]["area"]["code"] == "GATE-A"
        assert client.get("/api/v1/auth/me").status_code == 200
        logout = client.post(
            "/api/v1/auth/logout", headers={"X-CSRF-Token": login.get_json()["csrf_token"]}
        )
        assert logout.status_code == 204
        assert client.get("/api/v1/auth/me").status_code == 401

        with engine.connect() as connection:
            sessions = (
                connection.execute(sa.text("SELECT revoke_reason FROM auth_sessions"))
                .scalars()
                .all()
            )
            events = connection.execute(
                sa.text("SELECT event_type, result FROM audit_logs ORDER BY occurred_at")
            ).all()
            last_login = connection.execute(
                sa.text("SELECT last_login_at FROM users WHERE username = 'khoa.tran'")
            ).scalar_one()
        assert sessions == ["logout"]
        assert ("auth.login", "FAILURE") in [tuple(row) for row in events]
        assert ("auth.logout", "SUCCESS") in [tuple(row) for row in events]
        assert last_login is not None

        with pytest.raises(IntegrityError):
            with engine.begin() as connection:
                connection.execute(
                    sa.text(
                        "UPDATE auth_sessions SET revoked_at = NULL WHERE revoke_reason = 'logout'"
                    )
                )
    finally:
        command.downgrade(config, "base")
        engine.dispose()
