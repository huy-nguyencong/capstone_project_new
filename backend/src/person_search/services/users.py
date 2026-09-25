from __future__ import annotations

import base64
import binascii
import re
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime

from person_search.auth.passwords import PasswordHasher, WeakPasswordError
from person_search.services.audit import AuditEvent, record_audit
from person_search.storage.postgres.errors import DuplicateEntityError
from person_search.storage.postgres.models import (
    Area,
    AuditResult,
    User,
    UserRole,
    UserStatus,
)
from person_search.storage.postgres.unit_of_work import UnitOfWork

MAX_USER_PAGE = 100
USERNAME_PATTERN = re.compile(r"^[a-z0-9._]{3,32}$")
DISPLAY_NAME_MAX_LENGTH = 200


class UserRequestError(ValueError):
    def __init__(self, code: str, message: str, *, field: str | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.field = field


class UserConflictError(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


class UserNotFoundError(LookupError):
    pass


@dataclass(frozen=True, slots=True)
class AreaView:
    id: uuid.UUID
    code: str
    name: str


@dataclass(frozen=True, slots=True)
class UserView:
    id: uuid.UUID
    username: str
    display_name: str
    role: UserRole
    status: UserStatus
    area: AreaView | None
    last_login_at: datetime | None
    created_at: datetime | None
    version: int


@dataclass(frozen=True, slots=True)
class UserListQuery:
    role: UserRole | None = None
    status: UserStatus | None = None
    query: str | None = None
    limit: int = 20
    cursor: str | None = None


@dataclass(frozen=True, slots=True)
class UserPage:
    items: list[UserView]
    next_cursor: str | None


def _encode_cursor(user_id: uuid.UUID) -> str:
    return base64.urlsafe_b64encode(user_id.bytes).decode().rstrip("=")


def _decode_cursor(cursor: str) -> uuid.UUID:
    try:
        padded = cursor + "=" * (-len(cursor) % 4)
        raw = base64.urlsafe_b64decode(padded)
        if len(raw) != 16:
            raise ValueError("invalid UUID length")
        return uuid.UUID(bytes=raw)
    except (ValueError, binascii.Error) as error:
        raise UserRequestError("invalid_cursor", "Cursor is invalid.") from error


def _now() -> datetime:
    return datetime.now(UTC)


class UserService:
    def __init__(
        self,
        unit_of_work_factory: Callable[[], UnitOfWork],
        *,
        hasher: PasswordHasher,
        clock: Callable[[], datetime] = _now,
    ) -> None:
        self._unit_of_work_factory = unit_of_work_factory
        self._hasher = hasher
        self._clock = clock

    def list_areas(self) -> list[AreaView]:
        with self._unit_of_work_factory() as work:
            assert work.repositories is not None
            rows = work.repositories.areas.page(limit=100)
            rows.sort(key=lambda area: (area.code, area.id))
            return [AreaView(row.id, row.code, row.name) for row in rows]

    def list_users(self, query: UserListQuery) -> UserPage:
        if query.limit < 1 or query.limit > MAX_USER_PAGE:
            raise UserRequestError(
                "invalid_limit", "limit must be between 1 and 100.", field="limit"
            )
        search = query.query.strip() if query.query else None
        if search and len(search) > 200:
            raise UserRequestError("invalid_query", "Search query is too long.", field="q")
        after_id = _decode_cursor(query.cursor) if query.cursor else None
        with self._unit_of_work_factory() as work:
            assert work.repositories is not None
            repositories = work.repositories
            rows = repositories.users.search(
                role=query.role,
                status=query.status,
                query=search,
                after_id=after_id,
                limit=query.limit + 1,
            )
            has_more = len(rows) > query.limit
            rows = rows[: query.limit]
            items = [self._view(repositories, row) for row in rows]
        cursor = _encode_cursor(rows[-1].id) if has_more and rows else None
        return UserPage(items, cursor)

    def get_user(self, user_id: uuid.UUID) -> UserView:
        with self._unit_of_work_factory() as work:
            assert work.repositories is not None
            user = work.repositories.users.get(user_id)
            if user is None:
                raise UserNotFoundError
            return self._view(work.repositories, user)

    def create_user(
        self,
        *,
        actor_id: uuid.UUID,
        username: str,
        display_name: str,
        password: str,
        role: UserRole,
        area_id: uuid.UUID | None,
    ) -> UserView:
        username = self._validate_username(username)
        display_name = self._validate_display_name(display_name)
        self._validate_managed_role(role, area_id)
        try:
            password_hash = self._hasher.hash(password)
        except WeakPasswordError as error:
            raise UserRequestError("weak_password", str(error), field="password") from error
        with self._unit_of_work_factory() as work:
            assert work.repositories is not None
            repositories = work.repositories
            self._require_admin(repositories, actor_id)
            if repositories.users.get_by_username(username) is not None:
                raise UserConflictError("username_taken", "Username is already in use.")
            self._require_area(repositories, area_id)
            user = User(
                id=uuid.uuid4(),
                username=username,
                display_name=display_name,
                password_hash=password_hash,
                role=role,
                status=UserStatus.ACTIVE,
                assigned_area_id=area_id,
                version=1,
            )
            repositories.users.add(user)
            record_audit(
                repositories,
                event_type=AuditEvent.USER_CREATED,
                result=AuditResult.SUCCESS,
                target_type="user",
                target_id=user.id,
                actor=repositories.users.get(actor_id),
                metadata={"username": username, "role": role.value},
            )
            try:
                work.commit()
            except DuplicateEntityError as error:
                raise UserConflictError("username_taken", "Username is already in use.") from error
            return self._view(repositories, user)

    def update_user(
        self,
        user_id: uuid.UUID,
        *,
        actor_id: uuid.UUID,
        display_name: str,
        role: UserRole,
        area_id: uuid.UUID | None,
        version: int,
        password: str | None = None,
    ) -> UserView:
        display_name = self._validate_display_name(display_name)
        self._validate_managed_role(role, area_id)
        password_hash = None
        if password is not None:
            try:
                password_hash = self._hasher.hash(password)
            except WeakPasswordError as error:
                raise UserRequestError("weak_password", str(error), field="password") from error
        with self._unit_of_work_factory() as work:
            assert work.repositories is not None
            repositories = work.repositories
            self._require_admin(repositories, actor_id)
            user = repositories.users.get(user_id)
            if user is None:
                raise UserNotFoundError
            self._ensure_managed_user(user)
            if user.version != version:
                raise UserConflictError("version_conflict", "User was changed by another request.")
            self._require_area(repositories, area_id)
            permission_changed = user.role is not role or user.assigned_area_id != area_id
            values: dict[str, object] = {
                "display_name": display_name,
                "role": role,
                "assigned_area_id": area_id,
            }
            if password_hash is not None:
                values["password_hash"] = password_hash
            if not repositories.users.update_if_version(
                user.id, expected_version=version, values=values
            ):
                raise UserConflictError(
                    "version_conflict", "User was changed by another request."
                )
            repositories.users.refresh(user)
            if permission_changed:
                repositories.auth_sessions.revoke_for_user(
                    user.id, at=self._clock(), reason="permissions_changed"
                )
            event = AuditEvent.USER_ROLE_CHANGED if permission_changed else AuditEvent.USER_UPDATED
            record_audit(
                repositories,
                event_type=event,
                result=AuditResult.SUCCESS,
                target_type="user",
                target_id=user.id,
                actor=repositories.users.get(actor_id),
                metadata={"username": user.username, "role": role.value},
            )
            work.commit()
            return self._view(repositories, user)

    def change_status(
        self, user_id: uuid.UUID, *, actor_id: uuid.UUID, action: str
    ) -> UserView:
        desired = {
            "lock": UserStatus.LOCKED,
            "unlock": UserStatus.ACTIVE,
            "deactivate": UserStatus.INACTIVE,
        }[action]
        with self._unit_of_work_factory() as work:
            assert work.repositories is not None
            repositories = work.repositories
            self._require_admin(repositories, actor_id)
            user = repositories.users.get(user_id)
            if user is None:
                raise UserNotFoundError
            if user.id == actor_id and action in {"lock", "deactivate"}:
                raise UserConflictError("cannot_lock_self", "You cannot disable your own account.")
            self._ensure_managed_user(user)
            if action == "unlock" and user.status is UserStatus.INACTIVE:
                raise UserConflictError(
                    "account_inactive", "An inactive account cannot be unlocked."
                )
            if user.status is not desired:
                user.status = desired
                user.version += 1
                if desired is not UserStatus.ACTIVE:
                    repositories.auth_sessions.revoke_for_user(
                        user.id, at=self._clock(), reason=f"user_{desired.value.lower()}"
                    )
                record_audit(
                    repositories,
                    event_type=AuditEvent.USER_STATUS_CHANGED,
                    result=AuditResult.SUCCESS,
                    target_type="user",
                    target_id=user.id,
                    actor=repositories.users.get(actor_id),
                    metadata={"username": user.username, "status": desired.value},
                )
                work.commit()
            return self._view(repositories, user)

    @staticmethod
    def _validate_username(value: str) -> str:
        normalized = value.strip().lower() if isinstance(value, str) else ""
        if not USERNAME_PATTERN.fullmatch(normalized):
            raise UserRequestError(
                "invalid_username",
                "Username must contain 3-32 lowercase letters, numbers, dots, or underscores.",
                field="username",
            )
        return normalized

    @staticmethod
    def _validate_display_name(value: str) -> str:
        normalized = value.strip() if isinstance(value, str) else ""
        if not normalized or len(normalized) > DISPLAY_NAME_MAX_LENGTH:
            raise UserRequestError(
                "invalid_display_name",
                "Display name is required and may contain at most 200 characters.",
                field="display_name",
            )
        return normalized

    @staticmethod
    def _validate_managed_role(role: UserRole, area_id: uuid.UUID | None) -> None:
        if role not in {UserRole.OPERATOR, UserRole.VIEWER}:
            raise UserRequestError(
                "invalid_role", "Only OPERATOR and VIEWER can be managed.", field="role"
            )
        if role is UserRole.OPERATOR and area_id is None:
            raise UserRequestError(
                "operator_area_required", "Operator must be assigned to an area.", field="area_id"
            )
        if role is UserRole.VIEWER and area_id is not None:
            raise UserRequestError(
                "viewer_area_forbidden", "Viewer cannot be assigned to an area.", field="area_id"
            )

    @staticmethod
    def _require_area(repositories: object, area_id: uuid.UUID | None) -> None:
        if area_id is not None and repositories.areas.get(area_id) is None:  # type: ignore[attr-defined]
            raise UserRequestError("area_not_found", "Area does not exist.", field="area_id")

    @staticmethod
    def _require_admin(repositories: object, actor_id: uuid.UUID) -> User:
        actor = repositories.users.get(actor_id)  # type: ignore[attr-defined]
        if (
            actor is None
            or actor.status is not UserStatus.ACTIVE
            or actor.role is not UserRole.ADMIN
        ):
            raise UserConflictError("forbidden", "Only an active Admin can manage users.")
        return actor

    @staticmethod
    def _ensure_managed_user(user: User) -> None:
        if user.role is UserRole.ADMIN:
            raise UserConflictError(
                "protected_admin_account", "Admin accounts cannot be changed here."
            )

    @staticmethod
    def _view(repositories: object, user: User) -> UserView:
        area: Area | None = None
        if user.assigned_area_id is not None:
            area = repositories.areas.get(user.assigned_area_id)  # type: ignore[attr-defined]
        return UserView(
            id=user.id,
            username=user.username,
            display_name=user.display_name,
            role=user.role,
            status=user.status,
            area=AreaView(area.id, area.code, area.name) if area else None,
            last_login_at=user.last_login_at,
            created_at=getattr(user, "created_at", None),
            version=user.version,
        )
