"""Load and close the complete production candidate before config activation."""

from __future__ import annotations

import argparse
import uuid
from pathlib import Path
from types import SimpleNamespace

from person_search.ai.config_loader import ProductionModelCandidateLoader
from person_search.ai.configuration import ConfigApplyCoordinator
from person_search.ai.registry import load_registry


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--registry", type=Path, required=True)
    parser.add_argument("--artifact-root", type=Path, required=True)
    parser.add_argument("--config-root", type=Path, required=True)
    args = parser.parse_args()
    registry = load_registry(
        args.registry,
        artifact_root=args.artifact_root,
        preflight_available={"yolo11n_coco", "bytetrack_v1", "rasa_cuhk_pedes_v1"},
    )
    selection = registry.resolve("yolo11n_coco", "bytetrack_v1")
    row = SimpleNamespace(
        id=uuid.uuid4(),
        version="candidate-smoke-v1",
        detector_name=selection.detector.id,
        detector_version=selection.detector.version,
        tracker_name=selection.tracker.id,
        tracker_version=selection.tracker.version,
        encoder_name=selection.encoder.id,
        encoder_version=selection.encoder.version,
        encoder_dimension=selection.encoder.dimension,
        checkpoint_sha256=selection.encoder.artifact.sha256,
    )
    loader = ProductionModelCandidateLoader.from_environment(
        artifact_root=args.artifact_root,
        config_root=args.config_root,
    )
    coordinator = ConfigApplyCoordinator(registry, loader=loader)
    prepared = coordinator.prepare(row)
    coordinator.activate(prepared)
    print(
        "candidate config loaded and closed: "
        f"{prepared.selection.detector.id}/"
        f"{prepared.selection.tracker.id}/"
        f"{prepared.selection.encoder.id}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
