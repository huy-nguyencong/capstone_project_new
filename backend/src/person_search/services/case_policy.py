"""Authorization contract for creating operator-owned cases."""

from __future__ import annotations

import uuid

from person_search.storage.postgres.models.enums import UserRole


class CaseOwnerNotAllowedError(PermissionError):
    """Raised when the authenticated actor cannot own a Case."""


def owner_id_from_authenticated_actor(actor_id: uuid.UUID, role: UserRole) -> uuid.UUID:
    """Derive ownership from the authenticated actor, never from request input."""

    if role is not UserRole.OPERATOR:
        raise CaseOwnerNotAllowedError("Only an authenticated Operator can own a Case.")
    return actor_id
