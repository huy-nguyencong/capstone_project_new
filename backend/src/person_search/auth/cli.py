from __future__ import annotations

import argparse
import getpass
import os
import sys
import uuid
from collections.abc import Callable, Sequence

from dotenv import load_dotenv
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from person_search.auth.passwords import PasswordHasher, WeakPasswordError, validate_new_password
from person_search.config import PostgresSettings
from person_search.services.audit import AuditEvent, record_audit
from person_search.services.auth import USERNAME_MAX_LENGTH, normalize_username
from person_search.storage.postgres.errors import DuplicateEntityError
from person_search.storage.postgres.models import Area, AuditResult, User, UserRole, UserStatus
from person_search.storage.postgres.unit_of_work import UnitOfWork

PASSWORD_ENVIRONMENT = "PERSON_SEARCH_NEW_USER_PASSWORD"


class CommandError(RuntimeError):
    pass


def read_password(prompt: Callable[[str], str] = getpass.getpass) -> str:
    from_environment = os.environ.get(PASSWORD_ENVIRONMENT)
    if from_environment:
        return from_environment
    first = prompt("Password: ")
    if first != prompt("Repeat password: "):
        raise CommandError("Passwords do not match.")
    return first


def create_user(
    unit_of_work_factory: Callable[[], UnitOfWork],
    hasher: PasswordHasher,
    *,
    username: str,
    display_name: str,
    role: UserRole,
    password: str,
    area_code: str | None,
) -> uuid.UUID:
    normalized = normalize_username(username)
    if not normalized or len(normalized) > USERNAME_MAX_LENGTH:
        raise CommandError("Username must have between 1 and 100 characters.")
    if not display_name.strip():
        raise CommandError("Display name must not be blank.")
    if role is UserRole.OPERATOR and not area_code:
        raise CommandError("Operator accounts require --area.")
    if role is not UserRole.OPERATOR and area_code:
        raise CommandError("Only Operator accounts can have an area.")
    try:
        validate_new_password(password)
    except WeakPasswordError as error:
        raise CommandError(str(error)) from error
    with unit_of_work_factory() as work:
        assert work.session is not None and work.repositories is not None
        area_id = None
        if area_code:
            area = work.session.scalars(select(Area).where(Area.code == area_code)).one_or_none()
            if area is None:
                raise CommandError(f"Area '{area_code}' does not exist.")
            area_id = area.id
        user = User(
            id=uuid.uuid4(),
            username=normalized,
            password_hash=hasher.hash(password),
            display_name=display_name.strip(),
            role=role,
            status=UserStatus.ACTIVE,
            assigned_area_id=area_id,
        )
        work.repositories.users.add(user)
        record_audit(
            work.repositories,
            event_type=AuditEvent.USER_CREATED,
            result=AuditResult.SUCCESS,
            target_type="user",
            target_id=user.id,
            metadata={"username": normalized, "role": role.value, "source": "cli"},
        )
        try:
            work.commit()
        except DuplicateEntityError as error:
            raise CommandError(f"Username '{normalized}' already exists.") from error
        return user.id


def set_password(
    unit_of_work_factory: Callable[[], UnitOfWork],
    hasher: PasswordHasher,
    *,
    username: str,
    password: str,
) -> None:
    try:
        validate_new_password(password)
    except WeakPasswordError as error:
        raise CommandError(str(error)) from error
    normalized = normalize_username(username)
    with unit_of_work_factory() as work:
        assert work.repositories is not None
        user = work.repositories.users.get_by_username(normalized)
        if user is None:
            raise CommandError(f"User '{normalized}' does not exist.")
        user.password_hash = hasher.hash(password)
        record_audit(
            work.repositories,
            event_type=AuditEvent.USER_UPDATED,
            result=AuditResult.SUCCESS,
            target_type="user",
            target_id=user.id,
            metadata={"fields": ["password"], "source": "cli"},
        )
        work.commit()


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="person-search-user")
    commands = parser.add_subparsers(dest="command", required=True)
    create = commands.add_parser("create", help="Create an account.")
    create.add_argument("--username", required=True)
    create.add_argument("--display-name", required=True)
    create.add_argument("--role", required=True, choices=[role.value for role in UserRole])
    create.add_argument("--area", help="Area code, required for OPERATOR.")
    reset = commands.add_parser("set-password", help="Replace an account password.")
    reset.add_argument("--username", required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    load_dotenv()
    arguments = _parser().parse_args(argv)
    engine = create_engine(PostgresSettings.from_environment(os.environ).dsn)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    hasher = PasswordHasher()
    try:
        password = read_password()
        if arguments.command == "create":
            user_id = create_user(
                lambda: UnitOfWork(factory),
                hasher,
                username=arguments.username,
                display_name=arguments.display_name,
                role=UserRole(arguments.role),
                password=password,
                area_code=arguments.area,
            )
            print(f"Created user {normalize_username(arguments.username)} ({user_id}).")
        else:
            set_password(
                lambda: UnitOfWork(factory), hasher, username=arguments.username, password=password
            )
            print(f"Password updated for {normalize_username(arguments.username)}.")
    except CommandError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    finally:
        engine.dispose()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
