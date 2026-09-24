"""Small dependency container used by the application factory and tests."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


class DependencyNotConfiguredError(LookupError):
    """Raised when a requested dependency has not been registered."""


@dataclass(slots=True)
class DependencyContainer:
    """Explicit registry for adapters that will be introduced in later tasks."""

    _values: dict[str, Any] = field(default_factory=dict)

    def register(self, name: str, value: Any) -> None:
        """Register a dependency and reject accidental duplicate wiring."""

        if name in self._values:
            raise ValueError(f"Dependency '{name}' is already registered.")
        self._values[name] = value

    def get(self, name: str) -> Any:
        """Return a configured dependency or raise a domain-specific error."""

        try:
            return self._values[name]
        except KeyError as exc:
            raise DependencyNotConfiguredError(
                f"Dependency '{name}' has not been configured."
            ) from exc
