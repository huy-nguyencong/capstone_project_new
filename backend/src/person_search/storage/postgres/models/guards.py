"""ORM-side guards mirrored by PostgreSQL triggers."""


class ImmutableFieldError(ValueError):
    """Raised before flush when immutable identity data is changed."""
