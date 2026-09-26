"""Atomic model configuration preparation and version-aware worker cache."""

from __future__ import annotations

import threading
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from person_search.ai.registry import ModelRegistry, PipelineSelection, RegistryValidationError


def _fingerprint(config: Any) -> tuple[Any, ...]:
    return (
        config.id,
        config.version,
        config.detector_name,
        config.detector_version,
        config.tracker_name,
        config.tracker_version,
        config.encoder_name,
        config.encoder_version,
        config.encoder_dimension,
        config.checkpoint_sha256,
    )


@dataclass(frozen=True, slots=True)
class PreparedAIConfig:
    config_id: UUID
    version: str
    fingerprint: tuple[Any, ...]
    selection: PipelineSelection


class VersionedAIConfigCache:
    """Cache immutable registry resolutions without accepting mutated DB lineage."""

    def __init__(self, registry: ModelRegistry) -> None:
        self.registry = registry
        self._lock = threading.Lock()
        self._entries: dict[UUID, PreparedAIConfig] = {}
        self._active: PreparedAIConfig | None = None

    def prepare(self, config: Any) -> PreparedAIConfig:
        selection = self.registry.resolve_config(config)
        return PreparedAIConfig(config.id, config.version, _fingerprint(config), selection)

    def activate(self, prepared: PreparedAIConfig) -> None:
        with self._lock:
            self._entries[prepared.config_id] = prepared
            self._active = prepared

    def resolve(self, config: Any) -> PipelineSelection:
        fingerprint = _fingerprint(config)
        with self._lock:
            cached = self._entries.get(config.id)
        if cached is not None:
            if cached.fingerprint != fingerprint:
                raise RegistryValidationError(
                    "AI configuration lineage changed without a new configuration ID."
                )
            return cached.selection
        prepared = self.prepare(config)
        with self._lock:
            existing = self._entries.setdefault(prepared.config_id, prepared)
        if existing.fingerprint != prepared.fingerprint:
            raise RegistryValidationError("Concurrent AI configuration lineage conflict.")
        return existing.selection

    @property
    def active(self) -> PreparedAIConfig | None:
        with self._lock:
            return self._active


class ConfigApplyCoordinator:
    """Load a candidate completely before atomically exposing it as active."""

    def __init__(
        self,
        registry: ModelRegistry,
        *,
        loader: Callable[[Any, PipelineSelection], None] | None = None,
        cache: VersionedAIConfigCache | None = None,
    ) -> None:
        self.registry = registry
        self.loader = loader or (lambda _config, _selection: None)
        self.cache = cache or VersionedAIConfigCache(registry)

    def prepare(self, config: Any) -> PreparedAIConfig:
        prepared = self.cache.prepare(config)
        self.loader(config, prepared.selection)
        return prepared

    def activate(self, prepared: PreparedAIConfig) -> None:
        self.cache.activate(prepared)
