"""Generate a reproducible AI worker runtime and resource preflight report."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from person_search.ai.preflight import (
    PreflightConfigurationError,
    apply_resource_environment,
    load_resource_settings,
    run_preflight,
)
from person_search.ai.registry import RegistryMode, RegistryValidationError, load_registry


def _demo_loaders(registry):
    if registry.mode is not RegistryMode.DEMO:
        return {}
    from person_search.workers.pipeline import DemoDetector, DemoEncoder, DemoTracker

    factories = {
        "demo_detector": DemoDetector,
        "demo_tracker": DemoTracker,
        "demo_encoder": DemoEncoder,
    }
    return {
        entry.id: (lambda _entry, _device, factory=factories[entry.id]: factory())
        for entry in (*registry.detectors, *registry.trackers, registry.encoder)
    }


def _production_loaders(registry_path, artifact_root, opened):
    """Open real production adapters so the report reflects an actual model load."""

    from person_search.ai.detectors import build_yolo_detector, load_detector_settings
    from person_search.ai.encoders import build_rasa_image_encoder, load_rasa_settings
    from person_search.ai.trackers import build_bytetrack

    config_root = Path(__file__).resolve().parents[1] / "config"
    detector_config = os.getenv("PERSON_SEARCH_DETECTOR_CONFIG") or (
        config_root / "ultralytics_yolo_detector.json"
    )
    rasa_config = os.getenv("PERSON_SEARCH_RASA_CONFIG") or (
        config_root / "rasa_cuhk_pedes_runtime.json"
    )
    builders = {
        "ultralytics_yolo": lambda entry, device: build_yolo_detector(
            entry,
            artifact_root=artifact_root,
            device=device,
            settings=load_detector_settings(detector_config),
        ),
        "bytetrack": lambda entry, device: build_bytetrack(
            entry, artifact_root=artifact_root, device=device
        ),
        "rasa": lambda entry, device: build_rasa_image_encoder(
            entry,
            artifact_root=artifact_root,
            runtime_settings=load_rasa_settings(rasa_config),
            device=device,
        ),
    }
    # Builders only accept preflight-available entries; the probe itself is that evidence.
    candidates = load_registry(registry_path, artifact_root=artifact_root)
    probe_registry = load_registry(
        registry_path,
        artifact_root=artifact_root,
        preflight_available={
            entry.id
            for entry in (*candidates.detectors, *candidates.trackers, candidates.encoder)
            if entry is not None
        },
    )
    probe_entries = {
        entry.id: entry
        for entry in (*probe_registry.detectors, *probe_registry.trackers, probe_registry.encoder)
        if entry is not None
    }

    def loader(build):
        def load(entry, device):
            component = build(probe_entries[entry.id], device)
            component.open()
            opened.append(component)
            return component

        return load

    return {
        entry_id: loader(builders[entry.adapter_kind])
        for entry_id, entry in probe_entries.items()
        if entry.adapter_kind in builders
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--registry", required=True)
    parser.add_argument("--resource-config", default="config/ai_resources.json")
    parser.add_argument("--profile", default="local_cpu")
    parser.add_argument("--artifact-root")
    parser.add_argument("--workspace", default=".")
    parser.add_argument("--output")
    parser.add_argument("--allow-demo", action="store_true")
    parser.add_argument("--allow-not-ready", action="store_true")
    args = parser.parse_args()
    opened = []
    try:
        settings = load_resource_settings(args.resource_config, args.profile)
        apply_resource_environment(settings)
        registry = load_registry(
            args.registry,
            artifact_root=args.artifact_root,
            allow_demo=args.allow_demo,
        )
        if registry.mode is RegistryMode.DEMO:
            loaders = _demo_loaders(registry)
        else:
            loaders = _production_loaders(
                args.registry,
                Path(args.artifact_root or Path(args.registry).parent).resolve(),
                opened,
            )
        report = run_preflight(
            settings,
            registry,
            workspace=args.workspace,
            model_loaders=loaders,
        )
    except (PreflightConfigurationError, RegistryValidationError) as error:
        parser.error(str(error))
    finally:
        for component in reversed(opened):
            component.close()
    serialized = json.dumps(report.as_dict(), indent=2, sort_keys=True)
    if args.output:
        target = Path(args.output)
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = target.with_suffix(target.suffix + ".tmp")
        temporary.write_text(serialized + "\n", encoding="utf-8")
        temporary.replace(target)
    print(serialized)
    return 0 if report.ready or args.allow_not_ready else 2


if __name__ == "__main__":
    raise SystemExit(main())
