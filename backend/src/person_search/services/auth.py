from __future__ import annotations

import os
import uuid
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from person_search.auth.passwords import MAX_PASSWORD_LENGTH, PasswordHasher
from person_search.auth.tokens import hash_session_token, new_session_token
from person_search.config import ConfigurationError
from person_search.services.audit import AuditEvent, record_audit
from person_search.storage.postgres.models import (
    AuditResult,
    AuthSession,
    User,
    UserRole,
    UserStatus,
)
from person_search.storage.postgres.unit_of_work import UnitOfWork

USERNAME_MAX_LENGTH = 100


class InvalidCredentialsError(Exception):
    pass


class AccountDisabledError(Exception):
    pass


class SessionInvalidError(Exception):
    def __init__(self, reason: str) -> None:
        super().__init__(f"Session is not valid: {reason}.")
        self.reason = reason


@dataclass(frozen=True, slots=True)
class AreaRef:
    id: uuid.UUID
    code: str
    name: str


@dataclass(frozen=True, slots=True)
class AuthenticatedUser:
    id: uuid.UUID
    username: str
    display_name: str
    role: UserRole
    area: AreaRef | None


@dataclass(frozen=True, slots=True)
class SessionGrant:
    user: AuthenticatedUser
    token: str
    expires_at: datetime


def _minutes(environment: Mapping[str, str], name: str, default: int) -> timedelta:
    raw = environment.get(name, str(default))
    try:
        value = int(raw)
    except ValueError as error:
        raise ConfigurationError(f"Environment variable {name} must be an integer.") from error
    if value < 1:
        raise ConfigurationError(f"Environment variable {name} must be positive.")
    return timedelta(minutes=value)


@dataclass(frozen=True, slots=True)
class SessionPolicy:
    absolute_ttl: timedelta = timedelta(hours=12)
    idle_timeout: timedelta = timedelta(minutes=30)
    touch_interval: timedelta = timedelta(minutes=1)

    @classmethod
    def from_environment(cls, environment: Mapping[str, str] | None = None) -> SessionPolicy:
        values = os.environ if environment is None else environment
        return cls(
            absolute_ttl=_minutes(values, "PERSON_SEARCH_SESSION_TTL_MINUTES", 720),
            idle_timeout=_minutes(values, "PERSON_SEARCH_SESSION_IDLE_MINUTES", 30),
        )


def normalize_username(username: str) -> str:
    return username.strip().lower() if isinstance(username, str) else ""


def _utc_now() -> datetime:
    return datetime.now(UTC)


class AuthService:
    def __init__(
        self,
        unit_of_work_factory: Callable[[], UnitOfWork],
        *,
        hasher: PasswordHasher,
        policy: SessionPolicy | None = None,
        clock: Callable[[], datetime] = _utc_now,
        token_factory: Callable[[], str] = new_session_token,
    ) -> None:
        self._unit_of_work_factory = unit_of_work_factory
        self._hasher = hasher
        self._policy = policy or SessionPolicy()
        self._clock = clock
        self._token_factory = token_factory

    @property
    def policy(self) -> SessionPolicy:
        return self._policy

    def login(
        self, username: str, password: str, *, previous_token: str | None = None
    ) -> SessionGrant:
        normalized = normalize_username(username)
        if not normalized or len(normalized) > USERNAME_MAX_LENGTH or not password:
            raise InvalidCredentialsError("Invalid username or password.")
        now = self._clock()
        with self._unit_of_work_factory() as work:
            repositories = work.repositories
            assert repositories is not None
            user = repositories.users.get_by_username(normalized)
            if user is None:
                self._hasher.verify_dummy(password)
                self._record_failure(work, None, normalized, "invalid_credentials")
                raise InvalidCredentialsError("Invalid username or password.")
            if not self._hasher.verify(user.password_hash, password):
                self._record_failure(work, user, normalized, "invalid_credentials")
                raise InvalidCredentialsError("Invalid username or password.")
            if user.status is not UserStatus.ACTIVE:
                self._record_failure(work, user, normalized, f"account_{user.status.value.lower()}")
                raise AccountDisabledError("Account is not active.")
            area = self._area_for(repositories, user)
            if user.role is UserRole.OPERATOR and area is None:
                self._record_failure(work, user, normalized, "operator_area_missing")
                raise AccountDisabledError("Operator has no assigned area.")
            if previous_token:
                self._revoke(repositories, previous_token, now, "rotated")
            if len(password) <= MAX_PASSWORD_LENGTH and self._hasher.needs_rehash(
                user.password_hash
            ):
                user.password_hash = self._hasher.hash(password)
            user.last_login_at = now
            token = self._token_factory()
            expires_at = now + self._policy.absolute_ttl
            repositories.auth_sessions.add(
                AuthSession(
                    id=uuid.uuid4(),
                    user_id=user.id,
                    token_hash=hash_session_token(token),
                    created_at=now,
                    last_seen_at=now,
                    expires_at=expires_at,
                )
            )
            record_audit(
                repositories,
                event_type=AuditEvent.AUTH_LOGIN,
                result=AuditResult.SUCCESS,
                target_type="user",
                target_id=user.id,
                actor=user,
            )
            work.commit()
            return SessionGrant(self._view(user, area), token, expires_at)

    def authenticate(self, token: str | None) -> AuthenticatedUser:
        if not token:
            raise SessionInvalidError("missing")
        now = self._clock()
        with self._unit_of_work_factory() as work:
            repositories = work.repositories
            assert repositories is not None
            session = repositories.auth_sessions.get_by_token_hash(hash_session_token(token))
            if session is None:
                raise SessionInvalidError("unknown")
            if session.revoked_at is not None:
                raise SessionInvalidError("revoked")
            user = repositories.users.get(session.user_id)
            if now >= session.expires_at or now - session.last_seen_at >= self._policy.idle_timeout:
                session.revoked_at = now
                session.revoke_reason = "expired"
                record_audit(
                    repositories,
                    event_type=AuditEvent.AUTH_SESSION_EXPIRED,
                    result=AuditResult.SUCCESS,
                    target_type="user",
                    target_id=session.user_id,
                    actor=user,
                )
                work.commit()
                raise SessionInvalidError("expired")
            if user is None or user.status is not UserStatus.ACTIVE:
                session.revoked_at = now
                session.revoke_reason = "user_disabled"
                work.commit()
                raise SessionInvalidError("user_disabled")
            area = self._area_for(repositories, user)
            if user.role is UserRole.OPERATOR and area is None:
                raise SessionInvalidError("user_disabled")
            if now - session.last_seen_at >= self._policy.touch_interval:
                session.last_seen_at = now
                work.commit()
            return self._view(user, area)

    def logout(self, token: str | None) -> None:
        if not token:
            return
        now = self._clock()
        with self._unit_of_work_factory() as work:
            repositories = work.repositories
            assert repositories is not None
            session = self._revoke(repositories, token, now, "logout")
            if session is None:
                return
            record_audit(
                repositories,
                event_type=AuditEvent.AUTH_LOGOUT,
                result=AuditResult.SUCCESS,
                target_type="user",
                target_id=session.user_id,
                actor=repositories.users.get(session.user_id),
            )
            work.commit()

    @staticmethod
    def _revoke(repositories: Any, token: str, now: datetime, reason: str) -> AuthSession | None:
        session = repositories.auth_sessions.get_by_token_hash(hash_session_token(token))
        if session is None or session.revoked_at is not None:
            return None
        session.revoked_at = now
        session.revoke_reason = reason
        return session

    @staticmethod
    def _area_for(repositories: Any, user: User) -> AreaRef | None:
        if user.assigned_area_id is None:
            return None
        area = repositories.areas.get(user.assigned_area_id)
        if area is None:
            return None
        return AreaRef(id=area.id, code=area.code, name=area.name)

    @staticmethod
    def _view(user: User, area: AreaRef | None) -> AuthenticatedUser:
        return AuthenticatedUser(
            id=user.id,
            username=user.username,
            display_name=user.display_name,
            role=user.role,
            area=area,
        )

    @staticmethod
    def _record_failure(work: Any, user: User | None, username: str, reason: str) -> None:
        record_audit(
            work.repositories,
            event_type=AuditEvent.AUTH_LOGIN,
            result=AuditResult.FAILURE,
            target_type="user",
            target_id=user.id if user is not None else None,
            actor=user,
            metadata={"username": username, "reason": reason},
        )
        work.commit()
