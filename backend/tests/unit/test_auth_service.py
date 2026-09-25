from __future__ import annotations

from datetime import timedelta

import pytest
from auth_fakes import PASSWORD, AuthWorld

from person_search.auth.passwords import PasswordHasher, WeakPasswordError
from person_search.auth.tokens import csrf_matches, csrf_token_for, hash_session_token
from person_search.services.audit import AuditEvent
from person_search.services.auth import (
    AccountDisabledError,
    InvalidCredentialsError,
    SessionInvalidError,
    SessionPolicy,
)
from person_search.storage.postgres.models import AuditResult, UserRole, UserStatus

pytestmark = pytest.mark.unit


def events(world: AuthWorld) -> list[tuple[str, AuditResult]]:
    return [(entry.event_type, entry.result) for entry in world.database.audit_logs]


def test_password_hasher_verifies_and_rejects() -> None:
    hasher = PasswordHasher(time_cost=1, memory_cost=1024, parallelism=1)
    hashed = hasher.hash(PASSWORD)

    assert PASSWORD not in hashed
    assert hasher.verify(hashed, PASSWORD)
    assert not hasher.verify(hashed, "wrong-password")
    assert not hasher.verify("not-a-hash", PASSWORD)
    assert not hasher.verify(hashed, "x" * 1000)
    with pytest.raises(WeakPasswordError):
        hasher.hash("short")


def test_csrf_token_is_bound_to_session_token() -> None:
    token = csrf_token_for("session-a")

    assert csrf_matches("session-a", token)
    assert not csrf_matches("session-b", token)
    assert not csrf_matches("session-a", None)
    assert not csrf_matches(None, token)


@pytest.mark.parametrize("role", list(UserRole))
def test_login_creates_hashed_session_for_every_role(role: UserRole) -> None:
    world = AuthWorld()
    user = world.user("person.one", role)

    grant = world.service.login("  PERSON.ONE ", PASSWORD)

    assert grant.user.id == user.id
    assert grant.user.role is role
    assert (grant.user.area is not None) is (role is UserRole.OPERATOR)
    assert grant.expires_at == world.clock.now + timedelta(hours=12)
    [session] = world.database.sessions.values()
    assert session.token_hash == hash_session_token(grant.token)
    assert grant.token not in session.token_hash
    assert user.last_login_at == world.clock.now
    assert events(world) == [(AuditEvent.AUTH_LOGIN.value, AuditResult.SUCCESS)]


def test_unknown_user_and_wrong_password_fail_identically_without_leaking_password() -> None:
    world = AuthWorld()
    world.user("khoa", UserRole.OPERATOR)

    with pytest.raises(InvalidCredentialsError) as unknown:
        world.service.login("nobody", PASSWORD)
    with pytest.raises(InvalidCredentialsError) as wrong:
        world.service.login("khoa", "wrong-password")

    assert str(unknown.value) == str(wrong.value)
    assert world.database.sessions == {}
    assert events(world) == [(AuditEvent.AUTH_LOGIN.value, AuditResult.FAILURE)] * 2
    for entry in world.database.audit_logs:
        assert PASSWORD not in str(entry.event_metadata)
        assert "wrong-password" not in str(entry.event_metadata)
        assert entry.event_metadata["reason"] == "invalid_credentials"


@pytest.mark.parametrize("status", [UserStatus.LOCKED, UserStatus.INACTIVE, UserStatus.DELETED])
def test_disabled_account_cannot_login(status: UserStatus) -> None:
    world = AuthWorld()
    world.user("hung", UserRole.OPERATOR, status=status)

    with pytest.raises(AccountDisabledError):
        world.service.login("hung", PASSWORD)

    assert world.database.sessions == {}
    assert world.database.audit_logs[0].event_metadata["reason"] == f"account_{status.lower()}"


def test_disabled_account_with_wrong_password_reports_invalid_credentials() -> None:
    world = AuthWorld()
    world.user("hung", UserRole.OPERATOR, status=UserStatus.LOCKED)

    with pytest.raises(InvalidCredentialsError):
        world.service.login("hung", "wrong-password")


def test_operator_with_missing_area_cannot_login() -> None:
    world = AuthWorld()
    user = world.user("khoa", UserRole.OPERATOR)
    world.database.areas.clear()

    with pytest.raises(AccountDisabledError):
        world.service.login("khoa", PASSWORD)

    assert user.last_login_at is None


def test_authenticate_returns_actor_and_touches_session_after_interval() -> None:
    world = AuthWorld()
    world.user("lan", UserRole.VIEWER)
    grant = world.service.login("lan", PASSWORD)
    [session] = world.database.sessions.values()

    world.clock.advance(seconds=30)
    assert world.service.authenticate(grant.token).username == "lan"
    assert session.last_seen_at == world.clock.now - timedelta(seconds=30)

    world.clock.advance(minutes=2)
    world.service.authenticate(grant.token)
    assert session.last_seen_at == world.clock.now


@pytest.mark.parametrize("token", [None, "", "not-issued"])
def test_authenticate_rejects_missing_or_unknown_token(token: str | None) -> None:
    world = AuthWorld()

    with pytest.raises(SessionInvalidError):
        world.service.authenticate(token)


def test_idle_session_expires_and_is_audited() -> None:
    world = AuthWorld(SessionPolicy(idle_timeout=timedelta(minutes=30)))
    world.user("lan", UserRole.VIEWER)
    grant = world.service.login("lan", PASSWORD)

    world.clock.advance(minutes=31)
    with pytest.raises(SessionInvalidError) as expired:
        world.service.authenticate(grant.token)
    with pytest.raises(SessionInvalidError) as reused:
        world.service.authenticate(grant.token)

    assert expired.value.reason == "expired"
    assert reused.value.reason == "revoked"
    assert events(world)[-1] == (AuditEvent.AUTH_SESSION_EXPIRED.value, AuditResult.SUCCESS)


def test_absolute_session_lifetime_is_enforced_even_when_active() -> None:
    world = AuthWorld(SessionPolicy(absolute_ttl=timedelta(minutes=60)))
    world.user("lan", UserRole.VIEWER)
    grant = world.service.login("lan", PASSWORD)

    for _ in range(5):
        world.clock.advance(minutes=11)
        world.service.authenticate(grant.token)
    world.clock.advance(minutes=6)

    with pytest.raises(SessionInvalidError, match="expired"):
        world.service.authenticate(grant.token)


def test_locking_user_invalidates_existing_session() -> None:
    world = AuthWorld()
    user = world.user("khoa", UserRole.OPERATOR)
    grant = world.service.login("khoa", PASSWORD)

    user.status = UserStatus.LOCKED

    with pytest.raises(SessionInvalidError, match="user_disabled"):
        world.service.authenticate(grant.token)
    [session] = world.database.sessions.values()
    assert session.revoke_reason == "user_disabled"


def test_logout_revokes_session_and_is_idempotent() -> None:
    world = AuthWorld()
    world.user("admin", UserRole.ADMIN)
    grant = world.service.login("admin", PASSWORD)

    world.service.logout(grant.token)
    world.service.logout(grant.token)
    world.service.logout(None)

    with pytest.raises(SessionInvalidError, match="revoked"):
        world.service.authenticate(grant.token)
    assert [event for event, _ in events(world)].count(AuditEvent.AUTH_LOGOUT.value) == 1


def test_login_rotates_previous_session() -> None:
    world = AuthWorld()
    world.user("admin", UserRole.ADMIN)
    first = world.service.login("admin", PASSWORD)

    second = world.service.login("admin", PASSWORD, previous_token=first.token)

    assert first.token != second.token
    with pytest.raises(SessionInvalidError, match="revoked"):
        world.service.authenticate(first.token)
    assert world.service.authenticate(second.token).username == "admin"


def test_refresh_rotates_session_and_renews_absolute_lifetime() -> None:
    world = AuthWorld()
    world.user("admin", UserRole.ADMIN)
    first = world.service.login("admin", PASSWORD)
    world.clock.advance(minutes=10)

    refreshed = world.service.refresh(first.token)

    assert refreshed.token != first.token
    assert refreshed.expires_at == world.clock.now + timedelta(hours=12)
    old_session = next(
        session
        for session in world.database.sessions.values()
        if session.token_hash == hash_session_token(first.token)
    )
    assert old_session.revoke_reason == "refreshed"
    with pytest.raises(SessionInvalidError, match="revoked"):
        world.service.authenticate(first.token)
    assert world.service.authenticate(refreshed.token).username == "admin"


def test_refresh_rejects_expired_session() -> None:
    world = AuthWorld(SessionPolicy(idle_timeout=timedelta(minutes=30)))
    world.user("admin", UserRole.ADMIN)
    grant = world.service.login("admin", PASSWORD)
    world.clock.advance(minutes=31)

    with pytest.raises(SessionInvalidError, match="expired"):
        world.service.refresh(grant.token)


def test_outdated_password_hash_is_upgraded_on_login() -> None:
    world = AuthWorld()
    user = world.user("admin", UserRole.ADMIN)
    weak = PasswordHasher(time_cost=1, memory_cost=512, parallelism=1)
    user.password_hash = weak.hash(PASSWORD)

    world.service.login("admin", PASSWORD)

    assert not world.hasher.needs_rehash(user.password_hash)
    assert world.hasher.verify(user.password_hash, PASSWORD)
