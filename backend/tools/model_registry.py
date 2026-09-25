"""Validate and inspect a local AI model registry without loading model frameworks."""

from __future__ import annotations

import argparse
import json

from person_search.ai.registry import RegistryValidationError, load_registry


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--artifact-root")
    parser.add_argument("--allow-demo", action="store_true")
    parser.add_argument("--preflight-id", action="append", default=[])
    args = parser.parse_args()
    try:
        registry = load_registry(
            args.manifest,
            artifact_root=args.artifact_root,
            preflight_available=set(args.preflight_id),
            allow_demo=args.allow_demo,
        )
    except RegistryValidationError as error:
        parser.error(str(error))

    def statuses(entries):
        return [
            {
                "id": entry.id,
                "available": entry.available,
                "unavailable_reasons": list(entry.unavailable_reasons),
            }
            for entry in entries
        ]

    print(
        json.dumps(
            {
                "schema_version": registry.schema_version,
                "mode": registry.mode.value,
                "detectors": statuses(registry.detectors),
                "trackers": statuses(registry.trackers),
                "encoder": statuses((registry.encoder,))[0] if registry.encoder else None,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
