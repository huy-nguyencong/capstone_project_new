"""Domain-facing PostgreSQL persistence errors."""


class PersistenceError(RuntimeError):
    """Base persistence failure with no SQLAlchemy details leaking to services."""


class DuplicateEntityError(PersistenceError):
    pass


class ReferencedEntityError(PersistenceError):
    pass


class InvalidEntityError(PersistenceError):
    pass


class ConcurrentUpdateError(PersistenceError):
    pass
