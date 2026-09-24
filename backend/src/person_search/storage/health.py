"""Storage health aggregation with secret-safe failures."""

from __future__ import annotations

import logging
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Protocol

logger = logging.getLogger(__name__)


class HealthProbe(Protocol):
    name: str

    def check_health(self) -> None: ...


def redact_text(message: str, secrets: Iterable[str]) -> str:
    redacted = message
    for secret in secrets:
        if secret:
            redacted = redacted.replace(secret, "***")
    return redacted


@dataclass(frozen=True, slots=True)
class HealthSnapshot:
    status: str
    components: dict[str, dict[str, str]]

    @property
    def ready(self) -> bool:
        return self.status == "ok"

    def as_dict(self) -> dict[str, object]:
        return {"status": self.status, "components": self.components}


class StorageHealthService:
    def __init__(self, probes: Iterable[HealthProbe], *, secrets: Iterable[str] = ()) -> None:
        self._probes = tuple(probes)
        self._secrets = tuple(secrets)

    def check(self) -> HealthSnapshot:
        components: dict[str, dict[str, str]] = {}
        for probe in self._probes:
            try:
                probe.check_health()
                components[probe.name] = {"status": "ok"}
            except Exception as exc:  # health boundary isolates every dependency
                safe_error = redact_text(str(exc), self._secrets)
                logger.warning("Storage health check failed for %s: %s", probe.name, safe_error)
                components[probe.name] = {"status": "error", "error": "unavailable"}
        overall = "ok" if all(value["status"] == "ok" for value in components.values()) else "error"
        return HealthSnapshot(status=overall, components=components)
