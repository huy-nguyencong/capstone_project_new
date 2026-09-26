"""Fail-fast tests for the deployment-owned AI model registry."""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from person_search.ai.registry import (
    IncompatibleModelPairError,
    ModelUnavailableError,
    RegistryMode,
    RegistryValidationError,
    load_registry,
    registry_from_dict,
)
from person_search.api.errors import ApiError
from person_search.services.cameras import CameraService

pytestmark = [pytest.mark.unit, pytest.mark.contract]


def _artifact(root: Path, name: str) -> dict[str, str]:
    target = root / name
    target.write_text(f"artifact:{name}\n", encoding="utf-8")
    return {"path": name, "sha256": hashlib.sha256(target.read_bytes()).hexdigest()}


def _provenance() -> dict[str, object]:
    return {
        "package_name": "test-package",
        "package_version": "1.2.3",
        "source_url": "https://example.invalid/source",
        "weights_url": "https://example.invalid/weights",
        "license": "Apache-2.0",
        "approved_for_project": True,
        "review_note": "Approved synthetic unit-test artifact.",
    }


def manifest(root: Path) -> dict[str, object]:
    return {
        "schema_version": "model-registry/v1",
        "mode": "production",
        "detectors": [
            {
                "id": "detector_one",
                "display_name": "Detector One",
                "version": "1.0.0",
                "description": "Unit-test detector.",
                "adapter_kind": "yolox",
                "artifact": _artifact(root, "detector.bin"),
                "devices": ["cpu", "cuda"],
                "input_shape": [3, 640, 640],
                "provenance": _provenance(),
                "person_class_id": 0,
                "preprocessing_version": "rgb_v1",
            }
        ],
        "trackers": [
            {
                "id": "tracker_one",
                "display_name": "Tracker One",
                "version": "1.0.0",
                "description": "Unit-test tracker.",
                "adapter_kind": "bytetrack",
                "artifact": _artifact(root, "tracker.json"),
                "devices": ["cpu"],
                "input_shape": [6],
                "provenance": _provenance(),
                "compatible_detectors": ["detector_one"],
            }
        ],
        "encoder": {
            "id": "encoder_one",
            "display_name": "Encoder One",
            "version": "1.0.0",
            "description": "Unit-test RaSa-compatible encoder.",
            "adapter_kind": "rasa",
            "artifact": _artifact(root, "encoder.bin"),
            "devices": ["cpu", "cuda"],
            "input_shape": [3, 384, 128],
            "provenance": _provenance(),
            "dimension": 256,
            "normalized": True,
            "preprocessing_version": "rasa_v1",
        },
    }


def load_valid(root: Path):
    return registry_from_dict(
        manifest(root),
        artifact_root=root,
        preflight_available={"detector_one", "tracker_one", "encoder_one"},
    )


def test_valid_registry_resolves_only_allowlisted_compatible_models(tmp_path: Path) -> None:
    registry = load_valid(tmp_path)
    selection = registry.resolve("detector_one", "tracker_one")

    assert registry.mode is RegistryMode.PRODUCTION
    assert selection.encoder.dimension == 256
    assert selection.detector.available is True
    assert registry.public_catalog()["detectors"][0]["available"] is True
    with pytest.raises(AttributeError):
        selection.detector.available = False

    config = SimpleNamespace(
        detector_name="detector_one",
        detector_version="1.0.0",
        tracker_name="tracker_one",
        tracker_version="1.0.0",
        encoder_name="encoder_one",
        encoder_version="1.0.0",
        encoder_dimension=256,
        checkpoint_sha256=selection.encoder.artifact.sha256,
    )
    assert registry.resolve_config(config) == selection
    config.detector_version = "tampered"
    with pytest.raises(RegistryValidationError, match="detector_version"):
        registry.resolve_config(config)


@pytest.mark.parametrize("failure", ["missing", "checksum"])
def test_artifact_failure_makes_entry_unavailable(tmp_path: Path, failure: str) -> None:
    payload = manifest(tmp_path)
    detector = payload["detectors"][0]
    if failure == "missing":
        (tmp_path / "detector.bin").unlink()
    else:
        detector["artifact"]["sha256"] = "0" * 64
    registry = registry_from_dict(
        payload,
        artifact_root=tmp_path,
        preflight_available={"detector_one", "tracker_one", "encoder_one"},
    )

    assert registry.detectors[0].available is False
    assert registry.detectors[0].unavailable_reasons == (
        "artifact_missing" if failure == "missing" else "artifact_checksum_mismatch",
    )
    with pytest.raises(ModelUnavailableError):
        registry.resolve("detector_one", "tracker_one")


def test_production_availability_requires_preflight_and_license_approval(tmp_path: Path) -> None:
    payload = manifest(tmp_path)
    payload["encoder"]["provenance"]["approved_for_project"] = False
    registry = registry_from_dict(payload, artifact_root=tmp_path)

    assert registry.detectors[0].unavailable_reasons == ("preflight_pending",)
    assert registry.encoder.unavailable_reasons == (
        "license_not_approved",
        "preflight_pending",
    )


def test_resolve_rechecks_artifact_to_prevent_post_startup_tampering(tmp_path: Path) -> None:
    registry = load_valid(tmp_path)
    (tmp_path / "detector.bin").write_bytes(b"tampered")

    with pytest.raises(ModelUnavailableError, match="changed after validation"):
        registry.resolve("detector_one", "tracker_one")


def test_duplicate_id_unknown_adapter_and_bad_dimension_fail_fast(tmp_path: Path) -> None:
    payload = manifest(tmp_path)
    payload["trackers"][0]["id"] = "detector_one"
    with pytest.raises(RegistryValidationError, match="globally unique"):
        registry_from_dict(payload, artifact_root=tmp_path)

    payload = manifest(tmp_path)
    payload["detectors"][0]["adapter_kind"] = "arbitrary_python_class"
    with pytest.raises(RegistryValidationError, match="not supported"):
        registry_from_dict(payload, artifact_root=tmp_path)

    payload = manifest(tmp_path)
    payload["encoder"]["dimension"] = 512
    with pytest.raises(RegistryValidationError, match="256-dimensional"):
        registry_from_dict(payload, artifact_root=tmp_path)


def test_compatibility_references_and_selection_are_enforced(tmp_path: Path) -> None:
    payload = manifest(tmp_path)
    payload["trackers"][0]["compatible_detectors"] = ["not_registered"]
    with pytest.raises(RegistryValidationError, match="unknown detector"):
        registry_from_dict(payload, artifact_root=tmp_path)

    payload = manifest(tmp_path)
    second = copy.deepcopy(payload["detectors"][0])
    second["id"] = "detector_two"
    payload["detectors"].append(second)
    registry = registry_from_dict(
        payload,
        artifact_root=tmp_path,
        preflight_available={"detector_one", "detector_two", "tracker_one", "encoder_one"},
    )
    with pytest.raises(IncompatibleModelPairError):
        registry.resolve("detector_two", "tracker_one")


def test_manifest_rejects_availability_url_path_and_class_injection(tmp_path: Path) -> None:
    payload = manifest(tmp_path)
    payload["detectors"][0]["available"] = True
    with pytest.raises(RegistryValidationError, match="unknown.*available"):
        registry_from_dict(payload, artifact_root=tmp_path)

    payload = manifest(tmp_path)
    payload["detectors"][0]["artifact"]["path"] = "https://attacker/model.pt"
    with pytest.raises(RegistryValidationError, match="relative path"):
        registry_from_dict(payload, artifact_root=tmp_path)

    payload = manifest(tmp_path)
    payload["detectors"][0]["adapter_class"] = "attacker.Model"
    with pytest.raises(RegistryValidationError, match="adapter_class"):
        registry_from_dict(payload, artifact_root=tmp_path)


def test_demo_registry_is_separate_and_requires_explicit_opt_in() -> None:
    path = Path(__file__).parents[2] / "config" / "models.demo.json"
    with pytest.raises(RegistryValidationError, match="explicit allow_demo"):
        load_registry(path)

    registry = load_registry(path, allow_demo=True)
    assert registry.mode is RegistryMode.DEMO
    assert registry.resolve("demo_detector", "demo_tracker").encoder.available


def test_production_mode_rejects_demo_adapter_even_with_valid_artifact(tmp_path: Path) -> None:
    payload = manifest(tmp_path)
    payload["detectors"][0]["adapter_kind"] = "demo_detector"

    with pytest.raises(RegistryValidationError, match="not supported in production mode"):
        registry_from_dict(payload, artifact_root=tmp_path)


def test_production_startup_cannot_opt_into_demo_registry(monkeypatch) -> None:
    path = Path(__file__).parents[2] / "config" / "models.demo.json"
    monkeypatch.setenv("PERSON_SEARCH_MODEL_REGISTRY", str(path))
    monkeypatch.setenv("PERSON_SEARCH_ALLOW_DEMO_MODELS", "1")

    with pytest.raises(RegistryValidationError, match="explicit allow_demo"):
        CameraService.registry_from_environment("production")


def test_production_example_is_valid_but_has_no_claimed_availability() -> None:
    path = Path(__file__).parents[2] / "config" / "models.example.json"
    registry = load_registry(path)

    assert len(registry.detectors) == 4
    assert len(registry.trackers) == 2
    assert not any(entry.available for entry in (*registry.detectors, *registry.trackers))
    assert registry.encoder is not None and not registry.encoder.available


def test_api_accepts_only_ids_and_rejects_url_path_or_class_fields(tmp_path: Path) -> None:
    service = CameraService(lambda: None, object(), load_valid(tmp_path))
    base = {"detector_id": "detector_one", "tracker_id": "tracker_one", "version": None}
    for field in ("model_url", "artifact_path", "adapter_class"):
        with pytest.raises(ApiError) as error:
            service._configure({**base, field: "https://attacker.invalid/model"}, None)
        assert error.value.code == "invalid_config"


def test_loader_rejects_invalid_json_without_echoing_content(tmp_path: Path) -> None:
    path = tmp_path / "registry.json"
    path.write_text('{"password":"secret"', encoding="utf-8")
    with pytest.raises(RegistryValidationError) as error:
        load_registry(path)
    assert "secret" not in str(error.value)


def test_registry_file_round_trip(tmp_path: Path) -> None:
    payload = manifest(tmp_path)
    path = tmp_path / "registry.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    registry = load_registry(
        path,
        preflight_available={"detector_one", "tracker_one", "encoder_one"},
    )
    assert registry.resolve("detector_one", "tracker_one").tracker.id == "tracker_one"
