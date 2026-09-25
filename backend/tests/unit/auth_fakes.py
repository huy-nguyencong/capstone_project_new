from __future__ import annotations

import itertools
import uuid
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import Any

from person_search.auth.passwords import PasswordHasher
from person_search.services.auth import AuthService, SessionPolicy
from person_search.storage.postgres.models import (
    Area,
    AuditLog,
    AuthSession,
    User,
    UserRole,
    UserStatus,
)

START = datetime(2026, 9, 25, 8, 0, tzinfo=UTC)
PASSWORD = "correct-horse-battery"


class FakeUsers:
    def __init__(self, rows: dict[uuid.UUID, User]) -> None:
        self.rows = rows

    def get(self, user_id: uuid.UUID) -> User | None:
        return self.rows.get(user_id)

    def get_by_username(self, username: str) -> User | None:
        return next((user for user in self.rows.values() if user.username == username), None)

    def add(self, user: User) -> None:
        self.rows[user.id] = user


class FakeSessions:
    def __init__(self, rows: dict[uuid.UUID, AuthSession]) -> None:
        self.rows = rows

    def add(self, session: AuthSession) -> None:
        self.rows[session.id] = session

    def get_by_token_hash(self, token_hash: str) -> AuthSession | None:
        return next((row for row in self.rows.values() if row.token_hash == token_hash), None)


class FakeAudit:
    def __init__(self, rows: list[AuditLog]) -> None:
        self.rows = rows

    def add(self, entry: AuditLog) -> None:
        self.rows.append(entry)


class AuthDatabase:
    def __init__(self) -> None:
        self.users: dict[uuid.UUID, User] = {}
        self.areas: dict[uuid.UUID, Area] = {}
        self.sessions: dict[uuid.UUID, AuthSession] = {}
        self.audit_logs: list[AuditLog] = []
        self.commits = 0


class AuthUnitOfWork:
    def __init__(self, database: AuthDatabase) -> None:
        self.database = database
        self.session = None
        self.repositories: Any = None

    def __enter__(self) -> AuthUnitOfWork:
        self.repositories = SimpleNamespace(
            users=FakeUsers(self.database.users),
            areas=SimpleNamespace(get=self.database.areas.get),
            auth_sessions=FakeSessions(self.database.sessions),
            audit_logs=FakeAudit(self.database.audit_logs),
        )
        return self

    def commit(self) -> None:
        self.database.commits += 1

    def __exit__(self, *args: object) -> None:
        pass


class Clock:
    def __init__(self) -> None:
        self.now = START

    def __call__(self) -> datetime:
        return self.now

    def advance(self, **delta: float) -> None:
        self.now += timedelta(**delta)


class AuthWorld:
    def __init__(self, policy: SessionPolicy | None = None) -> None:
        self.database = AuthDatabase()
        self.clock = Clock()
        self.hasher = PasswordHasher(time_cost=1, memory_cost=1024, parallelism=1)
        tokens = itertools.count(1)
        self.service = AuthService(
            lambda: AuthUnitOfWork(self.database),  # type: ignore[arg-type,return-value]
            hasher=self.hasher,
            policy=policy or SessionPolicy(),
            clock=self.clock,
            token_factory=lambda: f"token-{next(tokens):04d}-{uuid.uuid4().hex}",
        )
        self.area = Area(id=uuid.uuid4(), code="GATE-A", name="Gate A")
        self.database.areas[self.area.id] = self.area

    def user(
        self,
        username: str,
        role: UserRole,
        *,
        status: UserStatus = UserStatus.ACTIVE,
        password: str = PASSWORD,
    ) -> User:
        user = User(
            id=uuid.uuid4(),
            username=username,
            password_hash=self.hasher.hash(password),
            display_name=username.title(),
            role=role,
            status=status,
            assigned_area_id=self.area.id if role is UserRole.OPERATOR else None,
        )
        self.database.users[user.id] = user
        return user
