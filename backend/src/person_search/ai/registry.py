"""Typed, immutable allowlist for AI model adapters and local artifacts."""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Collection, Mapping, Sequence
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path, PurePosixPath
from types import MappingProxyType
from typing import Any, Final
from urllib.parse import urlsplit


class RegistryValidationError(ValueError):
    """Raised when a deployment-owned registry manifest is invalid."""


class ModelNotFoundError(RegistryValidationError):
    pass


class ModelUnavailableError(RegistryValidationError):
    pass


class IncompatibleModelPairError(RegistryValidationError):
    pass


class RegistryMode(StrEnum):
    PRODUCTION = "production"
    DEMO = "demo"


class DeviceKind(StrEnum):
    CPU = "cpu"
    CUDA = "cuda"


PRODUCTION_ADAPTERS: Final = {
    "detector": frozenset({"ultralytics_yolo", "yolox"}),
    "tracker": frozenset({"bytetrack", "botsort"}),
    "encoder": frozenset({"rasa"}),
}
DEMO_ADAPTERS: Final = {
    "detector": frozenset({"demo_detector"}),
    "tracker": frozenset({"demo_tracker"}),
    "encoder": frozenset({"demo_encoder"}),
}

_ID_PATTERN = re.compile(r"^[a-z][a-z0-9_]{2,63}$")
_VERSION_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._+-]{0,63}$")
_SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")


def _mapping(value: object, location: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise RegistryValidationError(f"{location} must be an object.")
    return value


def _exact_keys(value: Mapping[str, Any], expected: set[str], location: str) -> None:
    unknown = set(value) - expected
    missing = expected - set(value)
    if unknown or missing:
        parts = []
        if missing:
            parts.append(f"missing {sorted(missing)}")
        if unknown:
            parts.append(f"unknown {sorted(unknown)}")
        raise RegistryValidationError(f"{location} has invalid fields: {', '.join(parts)}.")


def _text(value: object, location: str, *, limit: int = 200) -> str:
    if not isinstance(value, str) or not value.strip() or len(value.strip()) > limit:
        raise RegistryValidationError(f"{location} must be a non-empty string.")
    return value.strip()


def _identifier(value: object, location: str) -> str:
    result = _text(value, location, limit=64)
    if not _ID_PATTERN.fullmatch(result):
        raise RegistryValidationError(f"{location} must be a stable lowercase identifier.")
    return result


def _version(value: object, location: str) -> str:
    result = _text(value, location, limit=64)
    if not _VERSION_PATTERN.fullmatch(result):
        raise RegistryValidationError(f"{location} is not a valid pinned version.")
    return result


def _sha256(value: object, location: str) -> str:
    if not isinstance(value, str) or not _SHA256_PATTERN.fullmatch(value.lower()):
        raise RegistryValidationError(f"{location} must be a 64-character SHA-256.")
    return value.lower()


def _https_url(value: object, location: str) -> str:
    url = _text(value, location, limit=500)
    parsed = urlsplit(url)
    if parsed.scheme != "https" or not parsed.netloc or parsed.username or parsed.password:
        raise RegistryValidationError(f"{location} must be a credential-free HTTPS URL.")
    return url


def _positive_int(value: object, location: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise RegistryValidationError(f"{location} must be a positive integer.")
    return value


@dataclass(frozen=True, slots=True)
class ArtifactReference:
    relative_path: str
    sha256: str


@dataclass(frozen=True, slots=True)
class Provenance:
    package_name: str
    package_version: str
    source_url: str
    weights_url: str | None
    license: str
    approved_for_project: bool
    review_note: str


@dataclass(frozen=True, slots=True)
class RegistryEntryBase:
    id: str
    display_name: str
    version: str
    description: str
    adapter_kind: str
    artifact: ArtifactReference
    devices: tuple[DeviceKind, ...]
    input_shape: tuple[int, ...]
    provenance: Provenance
    available: bool
    unavailable_reasons: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class DetectorEntry(RegistryEntryBase):
    person_class_id: int
    preprocessing_version: str


@dataclass(frozen=True, slots=True)
class TrackerEntry(RegistryEntryBase):
    compatible_detectors: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class EncoderEntry(RegistryEntryBase):
    dimension: int
    normalized: bool
    preprocessing_version: str


@dataclass(frozen=True, slots=True)
class PipelineSelection:
    detector: DetectorEntry
    tracker: TrackerEntry
    encoder: EncoderEntry


@dataclass(frozen=True, slots=True)
class ModelRegistry:
    schema_version: str
    mode: RegistryMode
    detectors: tuple[DetectorEntry, ...]
    trackers: tuple[TrackerEntry, ...]
    encoder: EncoderEntry | None
    artifact_root: Path
    _detectors: Mapping[str, DetectorEntry] = field(init=False, repr=False, compare=False)
    _trackers: Mapping[str, TrackerEntry] = field(init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "_detectors", MappingProxyType({item.id: item for item in self.detectors})
        )
        object.__setattr__(
            self, "_trackers", MappingProxyType({item.id: item for item in self.trackers})
        )

    @classmethod
    def empty(cls) -> ModelRegistry:
        return cls("model-registry/v1", RegistryMode.PRODUCTION, (), (), None, Path.cwd())

    def detector(self, model_id: str) -> DetectorEntry:
        try:
            return self._detectors[model_id]
        except KeyError:
            raise ModelNotFoundError("Detector ID is not allowlisted.") from None

    def tracker(self, model_id: str) -> TrackerEntry:
        try:
            return self._trackers[model_id]
        except KeyError:
            raise ModelNotFoundError("Tracker ID is not allowlisted.") from None

    def resolve(self, detector_id: str, tracker_id: str) -> PipelineSelection:
        detector = self.detector(detector_id)
        tracker = self.tracker(tracker_id)
        if self.encoder is None:
            raise ModelUnavailableError("Encoder is not configured.")
        if not detector.available or not tracker.available or not self.encoder.available:
            raise ModelUnavailableError("One or more selected models are unavailable.")
        if detector.id not in tracker.compatible_detectors:
            raise IncompatibleModelPairError("Detector and Tracker are incompatible.")
        for entry in (detector, tracker, self.encoder):
            target = _resolved_artifact(entry.artifact, self.artifact_root)
            if not target.is_file() or _file_sha256(target) != entry.artifact.sha256:
                raise ModelUnavailableError("A selected model artifact changed after validation.")
        return PipelineSelection(detector, tracker, self.encoder)

    def resolve_config(self, config: Any) -> PipelineSelection:
        """Resolve and verify an immutable database configuration before model loading."""

        selection = self.resolve(config.detector_name, config.tracker_name)
        expected = (
            ("detector_version", selection.detector.version),
            ("tracker_version", selection.tracker.version),
            ("encoder_name", selection.encoder.id),
            ("encoder_version", selection.encoder.version),
            ("encoder_dimension", selection.encoder.dimension),
            ("checkpoint_sha256", selection.encoder.artifact.sha256),
        )
        for field_name, registered in expected:
            if getattr(config, field_name, None) != registered:
                raise RegistryValidationError(
                    f"Active configuration field {field_name} does not match the registry."
                )
        return selection

    def public_catalog(self) -> dict[str, Any]:
        def common(entry: RegistryEntryBase) -> dict[str, Any]:
            return {
                "id": entry.id,
                "name": entry.display_name,
                "description": entry.description,
                "meta": f"{entry.version} · {', '.join(entry.devices)}",
                "available": entry.available,
            }

        trackers = []
        for entry in self.trackers:
            trackers.append(
                {**common(entry), "compatible_detectors": list(entry.compatible_detectors)}
            )
        return {
            "detectors": [common(entry) for entry in self.detectors],
            "trackers": trackers,
            "encoder": (
                {
                    "name": self.encoder.display_name,
                    "version": self.encoder.version,
                    "dimension": self.encoder.dimension,
                    "available": self.encoder.available,
                }
                if self.encoder
                else None
            ),
        }


def _artifact(value: object, location: str) -> ArtifactReference:
    data = _mapping(value, location)
    _exact_keys(data, {"path", "sha256"}, location)
    raw_path = _text(data["path"], f"{location}.path", limit=300)
    if "://" in raw_path or "\\" in raw_path:
        raise RegistryValidationError(f"{location}.path must be a POSIX-style relative path.")
    path = PurePosixPath(raw_path)
    if path.is_absolute() or ".." in path.parts or "." in path.parts:
        raise RegistryValidationError(f"{location}.path must remain inside artifact_root.")
    return ArtifactReference(raw_path, _sha256(data["sha256"], f"{location}.sha256"))


def _provenance(value: object, location: str) -> Provenance:
    data = _mapping(value, location)
    expected = {
        "package_name",
        "package_version",
        "source_url",
        "weights_url",
        "license",
        "approved_for_project",
        "review_note",
    }
    _exact_keys(data, expected, location)
    weights_url = data["weights_url"]
    if weights_url is not None:
        weights_url = _https_url(weights_url, f"{location}.weights_url")
    approved = data["approved_for_project"]
    if type(approved) is not bool:
        raise RegistryValidationError(f"{location}.approved_for_project must be boolean.")
    return Provenance(
        package_name=_text(data["package_name"], f"{location}.package_name"),
        package_version=_version(data["package_version"], f"{location}.package_version"),
        source_url=_https_url(data["source_url"], f"{location}.source_url"),
        weights_url=weights_url,
        license=_text(data["license"], f"{location}.license", limit=100),
        approved_for_project=approved,
        review_note=_text(data["review_note"], f"{location}.review_note", limit=500),
    )


def _devices(value: object, location: str) -> tuple[DeviceKind, ...]:
    if not isinstance(value, list) or not value:
        raise RegistryValidationError(f"{location} must be a non-empty list.")
    try:
        devices = tuple(DeviceKind(item) for item in value)
    except (TypeError, ValueError):
        raise RegistryValidationError(f"{location} contains an unsupported device.") from None
    if len(set(devices)) != len(devices):
        raise RegistryValidationError(f"{location} contains duplicate devices.")
    return devices


def _input_shape(value: object, location: str) -> tuple[int, ...]:
    if not isinstance(value, list) or not 1 <= len(value) <= 4:
        raise RegistryValidationError(f"{location} must contain one to four dimensions.")
    return tuple(_positive_int(item, location) for item in value)


def _artifact_reasons(
    artifact: ArtifactReference,
    *,
    artifact_root: Path,
    approved: bool,
    preflight_passed: bool,
) -> tuple[str, ...]:
    reasons = []
    target = _resolved_artifact(artifact, artifact_root)
    if not target.is_file():
        reasons.append("artifact_missing")
    else:
        digest = _file_sha256(target)
        if digest != artifact.sha256:
            reasons.append("artifact_checksum_mismatch")
    if not approved:
        reasons.append("license_not_approved")
    if not preflight_passed:
        reasons.append("preflight_pending")
    return tuple(reasons)


def _resolved_artifact(artifact: ArtifactReference, artifact_root: Path) -> Path:
    root = artifact_root.resolve()
    target = (root / Path(*PurePosixPath(artifact.relative_path).parts)).resolve()
    if not target.is_relative_to(root):
        raise RegistryValidationError("Resolved artifact path escapes artifact_root.")
    return target


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _common_entry(
    data: Mapping[str, Any],
    *,
    kind: str,
    location: str,
    mode: RegistryMode,
    artifact_root: Path,
    preflight_available: Collection[str],
) -> dict[str, Any]:
    model_id = _identifier(data["id"], f"{location}.id")
    adapter = _identifier(data["adapter_kind"], f"{location}.adapter_kind")
    allowlist = DEMO_ADAPTERS if mode is RegistryMode.DEMO else PRODUCTION_ADAPTERS
    if adapter not in allowlist[kind]:
        raise RegistryValidationError(f"{location}.adapter_kind is not supported in {mode} mode.")
    artifact = _artifact(data["artifact"], f"{location}.artifact")
    provenance = _provenance(data["provenance"], f"{location}.provenance")
    preflight_passed = mode is RegistryMode.DEMO or model_id in preflight_available
    reasons = _artifact_reasons(
        artifact,
        artifact_root=artifact_root,
        approved=provenance.approved_for_project,
        preflight_passed=preflight_passed,
    )
    return {
        "id": model_id,
        "display_name": _text(data["display_name"], f"{location}.display_name"),
        "version": _version(data["version"], f"{location}.version"),
        "description": _text(data["description"], f"{location}.description", limit=500),
        "adapter_kind": adapter,
        "artifact": artifact,
        "devices": _devices(data["devices"], f"{location}.devices"),
        "input_shape": _input_shape(data["input_shape"], f"{location}.input_shape"),
        "provenance": provenance,
        "available": not reasons,
        "unavailable_reasons": reasons,
    }


def _entries(value: object, location: str) -> Sequence[Mapping[str, Any]]:
    if not isinstance(value, list) or not value:
        raise RegistryValidationError(f"{location} must be a non-empty list.")
    return [_mapping(item, f"{location}[{index}]") for index, item in enumerate(value)]


def registry_from_dict(
    payload: Mapping[str, Any],
    *,
    artifact_root: str | Path,
    preflight_available: Collection[str] = (),
    allow_demo: bool = False,
) -> ModelRegistry:
    """Validate a manifest and derive availability from local evidence."""

    _exact_keys(payload, {"schema_version", "mode", "detectors", "trackers", "encoder"}, "root")
    if payload["schema_version"] != "model-registry/v1":
        raise RegistryValidationError("Unsupported model registry schema_version.")
    try:
        mode = RegistryMode(payload["mode"])
    except (TypeError, ValueError):
        raise RegistryValidationError("root.mode must be production or demo.") from None
    if mode is RegistryMode.DEMO and not allow_demo:
        raise RegistryValidationError("Demo registry requires explicit allow_demo=True.")
    root = Path(artifact_root).resolve()
    if not root.is_dir():
        raise RegistryValidationError("artifact_root must be an existing directory.")

    detector_keys = {
        "id",
        "display_name",
        "version",
        "description",
        "adapter_kind",
        "artifact",
        "devices",
        "input_shape",
        "provenance",
        "person_class_id",
        "preprocessing_version",
    }
    tracker_keys = {
        "id",
        "display_name",
        "version",
        "description",
        "adapter_kind",
        "artifact",
        "devices",
        "input_shape",
        "provenance",
        "compatible_detectors",
    }
    encoder_keys = {
        "id",
        "display_name",
        "version",
        "description",
        "adapter_kind",
        "artifact",
        "devices",
        "input_shape",
        "provenance",
        "dimension",
        "normalized",
        "preprocessing_version",
    }
    detectors = []
    for index, data in enumerate(_entries(payload["detectors"], "root.detectors")):
        location = f"root.detectors[{index}]"
        _exact_keys(data, detector_keys, location)
        common = _common_entry(
            data,
            kind="detector",
            location=location,
            mode=mode,
            artifact_root=root,
            preflight_available=preflight_available,
        )
        person_class_id = data["person_class_id"]
        if isinstance(person_class_id, bool) or not isinstance(person_class_id, int):
            raise RegistryValidationError(f"{location}.person_class_id must be an integer.")
        detectors.append(
            DetectorEntry(
                **common,
                person_class_id=person_class_id,
                preprocessing_version=_version(
                    data["preprocessing_version"], f"{location}.preprocessing_version"
                ),
            )
        )

    trackers = []
    for index, data in enumerate(_entries(payload["trackers"], "root.trackers")):
        location = f"root.trackers[{index}]"
        _exact_keys(data, tracker_keys, location)
        compatible = data["compatible_detectors"]
        if not isinstance(compatible, list) or not compatible:
            raise RegistryValidationError(
                f"{location}.compatible_detectors must be a non-empty list."
            )
        compatible_ids = tuple(
            _identifier(item, f"{location}.compatible_detectors") for item in compatible
        )
        if len(set(compatible_ids)) != len(compatible_ids):
            raise RegistryValidationError(
                f"{location}.compatible_detectors contains duplicate IDs."
            )
        trackers.append(
            TrackerEntry(
                **_common_entry(
                    data,
                    kind="tracker",
                    location=location,
                    mode=mode,
                    artifact_root=root,
                    preflight_available=preflight_available,
                ),
                compatible_detectors=compatible_ids,
            )
        )

    encoder_data = _mapping(payload["encoder"], "root.encoder")
    _exact_keys(encoder_data, encoder_keys, "root.encoder")
    normalized = encoder_data["normalized"]
    if type(normalized) is not bool:
        raise RegistryValidationError("root.encoder.normalized must be boolean.")
    encoder = EncoderEntry(
        **_common_entry(
            encoder_data,
            kind="encoder",
            location="root.encoder",
            mode=mode,
            artifact_root=root,
            preflight_available=preflight_available,
        ),
        dimension=_positive_int(encoder_data["dimension"], "root.encoder.dimension"),
        normalized=normalized,
        preprocessing_version=_version(
            encoder_data["preprocessing_version"], "root.encoder.preprocessing_version"
        ),
    )

    all_ids = [entry.id for entry in (*detectors, *trackers, encoder)]
    if len(set(all_ids)) != len(all_ids):
        raise RegistryValidationError("Model IDs must be globally unique.")
    detector_ids = {entry.id for entry in detectors}
    for tracker in trackers:
        unknown = set(tracker.compatible_detectors) - detector_ids
        if unknown:
            raise RegistryValidationError(
                f"Tracker {tracker.id} references unknown detector IDs: {sorted(unknown)}."
            )
    if encoder.dimension != 256:
        raise RegistryValidationError("RaSa contract v1 requires a 256-dimensional encoder.")
    if not encoder.normalized:
        raise RegistryValidationError("RaSa contract v1 requires normalized embeddings.")
    return ModelRegistry(
        "model-registry/v1", mode, tuple(detectors), tuple(trackers), encoder, root
    )


def load_registry(
    manifest_path: str | Path,
    *,
    artifact_root: str | Path | None = None,
    preflight_available: Collection[str] = (),
    allow_demo: bool = False,
) -> ModelRegistry:
    path = Path(manifest_path).resolve()
    if not path.is_file():
        raise RegistryValidationError("Model registry manifest does not exist.")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise RegistryValidationError("Model registry manifest is not valid UTF-8 JSON.") from exc
    return registry_from_dict(
        _mapping(payload, "root"),
        artifact_root=artifact_root or path.parent,
        preflight_available=preflight_available,
        allow_demo=allow_demo,
    )
