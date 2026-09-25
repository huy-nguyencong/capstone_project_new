"""Transaction boundary for PostgreSQL repositories."""

from __future__ import annotations

from types import TracebackType

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from person_search.storage.postgres.errors import (
    DuplicateEntityError,
    InvalidEntityError,
    ReferencedEntityError,
)
from person_search.storage.postgres.repositories import Repositories


def map_integrity_error(error: IntegrityError) -> Exception:
    code = getattr(getattr(error, "orig", None), "sqlstate", None)
    if code == "23505":
        return DuplicateEntityError("An entity with the same unique value already exists.")
    if code == "23503":
        return ReferencedEntityError("The operation conflicts with a referenced entity.")
    return InvalidEntityError("The entity violates a database constraint.")


class UnitOfWork:
    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory
        self.session: Session | None = None
        self.repositories: Repositories | None = None

    def __enter__(self) -> UnitOfWork:
        self.session = self._session_factory()
        self.repositories = Repositories(self.session)
        return self

    def flush(self) -> None:
        assert self.session is not None
        try:
            self.session.flush()
        except IntegrityError as error:
            self.session.rollback()
            raise map_integrity_error(error) from error

    def commit(self) -> None:
        assert self.session is not None
        try:
            self.session.commit()
        except IntegrityError as error:
            self.session.rollback()
            raise map_integrity_error(error) from error

    def rollback(self) -> None:
        assert self.session is not None
        self.session.rollback()

    def __exit__(
        self,
        exception_type: type[BaseException] | None,
        exception: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        assert self.session is not None
        if exception_type is not None:
            self.session.rollback()
        self.session.close()
