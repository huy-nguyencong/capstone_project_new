from __future__ import annotations

import secrets

from argon2 import PasswordHasher as Argon2Hasher
from argon2.exceptions import InvalidHashError, VerificationError

MIN_PASSWORD_LENGTH = 8
MAX_PASSWORD_LENGTH = 256


class WeakPasswordError(ValueError):
    pass


def validate_new_password(password: str) -> None:
    if not isinstance(password, str) or len(password) < MIN_PASSWORD_LENGTH:
        raise WeakPasswordError(f"Password must have at least {MIN_PASSWORD_LENGTH} characters.")
    if len(password) > MAX_PASSWORD_LENGTH:
        raise WeakPasswordError(f"Password must have at most {MAX_PASSWORD_LENGTH} characters.")


class PasswordHasher:
    def __init__(
        self, *, time_cost: int = 3, memory_cost: int = 65536, parallelism: int = 4
    ) -> None:
        self._hasher = Argon2Hasher(
            time_cost=time_cost, memory_cost=memory_cost, parallelism=parallelism
        )
        self._dummy_hash = self._hasher.hash(secrets.token_urlsafe(16))

    def hash(self, password: str) -> str:
        validate_new_password(password)
        return self._hasher.hash(password)

    def verify(self, password_hash: str, password: str) -> bool:
        if len(password) > MAX_PASSWORD_LENGTH:
            return False
        try:
            return self._hasher.verify(password_hash, password)
        except (VerificationError, InvalidHashError):
            return False

    def verify_dummy(self, password: str) -> None:
        self.verify(self._dummy_hash, password[:MAX_PASSWORD_LENGTH])

    def needs_rehash(self, password_hash: str) -> bool:
        try:
            return self._hasher.check_needs_rehash(password_hash)
        except InvalidHashError:
            return True
