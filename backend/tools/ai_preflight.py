"""Generate a reproducible AI worker runtime and resource preflight report."""

from __future__ import annotations

import argparse
import json
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
    try:
        settings = load_resource_settings(args.resource_config, args.profile)
        apply_resource_environment(settings)
        registry = load_registry(
            args.registry,
            artifact_root=args.artifact_root,
            allow_demo=args.allow_demo,
        )
        report = run_preflight(
            settings,
            registry,
            workspace=args.workspace,
            model_loaders=_demo_loaders(registry),
        )
    except (PreflightConfigurationError, RegistryValidationError) as error:
        parser.error(str(error))
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
