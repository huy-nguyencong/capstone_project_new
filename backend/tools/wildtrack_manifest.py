"""Generate or verify the reproducible local WILDTRACK dataset manifest."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from person_search.datasets.wildtrack import (
    build_manifest,
    validate_query_set,
    verify_manifest,
    write_manifest,
)


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    subcommands = result.add_subparsers(dest="command", required=True)
    generate = subcommands.add_parser("generate", help="Generate a manifest from the dataset")
    generate.add_argument("--dataset-root", required=True, type=Path)
    generate.add_argument("--output", required=True, type=Path)
    verify = subcommands.add_parser("verify", help="Verify a dataset against a manifest")
    verify.add_argument("--dataset-root", required=True, type=Path)
    verify.add_argument("--manifest", required=True, type=Path)
    queries = subcommands.add_parser(
        "validate-queries", help="Validate evaluation queries against annotations"
    )
    queries.add_argument("--dataset-root", required=True, type=Path)
    queries.add_argument("--queries", required=True, type=Path)
    return result


def main() -> int:
    arguments = parser().parse_args()
    if arguments.command == "generate":
        manifest = build_manifest(arguments.dataset_root)
        write_manifest(manifest, arguments.output)
        print(
            f"Wrote {arguments.output}: {manifest['content']['file_count']} files, "
            f"{manifest['content']['total_bytes']} bytes, "
            f"manifest {manifest['manifest_sha256']}"
        )
        return 0
    if arguments.command == "verify":
        source = arguments.manifest
        payload = json.loads(source.read_text(encoding="utf-8"))
        errors = verify_manifest(arguments.dataset_root, payload)
        identity = payload["manifest_sha256"]
    else:
        source = arguments.queries
        payload = json.loads(source.read_text(encoding="utf-8"))
        errors = validate_query_set(arguments.dataset_root, payload)
        identity = f"{len(payload.get('queries', []))} queries"
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1
    print(f"Verified {source}: {identity}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
