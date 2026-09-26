"""Exercise the AIW-14 production RaSa image adapter in its child process."""

from __future__ import annotations

import argparse
import io
import json
import math

import av

from person_search.ai.encoders import (
    RasaImageQueryGateway,
    build_rasa_image_encoder,
    load_rasa_settings,
)
from person_search.ai.registry import load_registry


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--registry", required=True)
    parser.add_argument("--artifact-root", required=True)
    parser.add_argument("--settings", required=True)
    parser.add_argument("--video", required=True)
    parser.add_argument("--device", default="cpu")
    args = parser.parse_args()

    registry = load_registry(
        args.registry,
        artifact_root=args.artifact_root,
        preflight_available={"rasa_cuhk_pedes_v1"},
    )
    assert registry.encoder is not None
    encoder = build_rasa_image_encoder(
        registry.encoder,
        artifact_root=args.artifact_root,
        runtime_settings=load_rasa_settings(args.settings),
        device=args.device,
    )
    container = av.open(args.video)
    frame = None
    person = None
    try:
        frame = next(container.decode(video=0)).to_image().convert("RGB")
        person = frame.crop((816, 399, 1009, 888))
    finally:
        container.close()

    query_bytes = io.BytesIO()
    person.save(query_bytes, format="PNG")
    encoder.open()
    try:
        stored = encoder.encode(person)
        query = RasaImageQueryGateway(encoder).image(
            query_bytes.getvalue(),
            version=encoder.lineage.version,
            dimension=encoder.dimension,
        )
        maximum_delta = max(
            abs(left - right) for left, right in zip(stored.values, query, strict=True)
        )
        if maximum_delta > 1e-6:
            raise RuntimeError("Stored and query image vectors differ beyond tolerance.")
        payload = {
            "status": "ok",
            "dimension": stored.dimension,
            "normalized": stored.normalized,
            "norm": math.sqrt(sum(value * value for value in stored.values)),
            "repeat_max_delta": maximum_delta,
            "encoder_id": stored.encoder.registry_id,
            "encoder_version": stored.encoder.version,
            "artifact_sha256": stored.encoder.artifact_sha256,
            "inference_count": encoder.metrics.inference_count,
            "last_latency_ms": encoder.metrics.last_latency_ms,
        }
    finally:
        encoder.close()
        person.close()
        frame.close()
        query_bytes.close()
    print(json.dumps(payload, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
