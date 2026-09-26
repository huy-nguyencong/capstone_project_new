from __future__ import annotations

import uuid
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from person_search.ai.configuration import ConfigApplyCoordinator, VersionedAIConfigCache
from person_search.ai.registry import RegistryValidationError


def config(**changes):
    values = {
        "id": uuid.uuid4(),
        "version": "config-v1",
        "detector_name": "detector_one",
        "detector_version": "1",
        "tracker_name": "tracker_one",
        "tracker_version": "1",
        "encoder_name": "encoder_one",
        "encoder_version": "encoder_v1",
        "encoder_dimension": 256,
        "checkpoint_sha256": "a" * 64,
    }
    values.update(changes)
    return SimpleNamespace(**values)


@pytest.mark.unit
def test_worker_cache_resolves_each_immutable_config_once():
    selection = object()
    registry = SimpleNamespace(resolve_config=Mock(return_value=selection))
    cache = VersionedAIConfigCache(registry)
    row = config()
    assert cache.resolve(row) is selection
    assert cache.resolve(row) is selection
    registry.resolve_config.assert_called_once_with(row)


@pytest.mark.unit
def test_cache_rejects_lineage_mutation_under_same_config_id():
    registry = SimpleNamespace(resolve_config=Mock(return_value=object()))
    cache = VersionedAIConfigCache(registry)
    row = config()
    cache.resolve(row)
    row.encoder_version = "mixed_space_v2"
    with pytest.raises(RegistryValidationError, match="lineage changed"):
        cache.resolve(row)


@pytest.mark.unit
def test_failed_candidate_load_does_not_replace_active_config():
    selections = iter(("old-selection", "new-selection"))
    registry = SimpleNamespace(resolve_config=Mock(side_effect=lambda _: next(selections)))
    fail_new = {"value": False}

    def loader(row, selection):
        if fail_new["value"]:
            raise RuntimeError("model load failed")

    coordinator = ConfigApplyCoordinator(registry, loader=loader)
    old = coordinator.prepare(config(version="old"))
    coordinator.activate(old)
    fail_new["value"] = True
    with pytest.raises(RuntimeError, match="load failed"):
        coordinator.prepare(config(version="new"))
    assert coordinator.cache.active is old


@pytest.mark.unit
def test_prepared_candidate_is_not_active_until_database_commit_signal():
    registry = SimpleNamespace(resolve_config=Mock(side_effect=("old", "candidate")))
    coordinator = ConfigApplyCoordinator(registry)
    old = coordinator.prepare(config(version="old"))
    coordinator.activate(old)
    coordinator.prepare(config(version="candidate"))
    assert coordinator.cache.active is old
