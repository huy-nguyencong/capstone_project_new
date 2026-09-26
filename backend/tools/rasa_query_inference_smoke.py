"""Run all AIW-15 query modes through the production RaSa child process."""

from __future__ import annotations

import argparse
import io
import json
import math

import av

from person_search.ai.encoders import build_rasa_query_gateway, load_rasa_settings
from person_search.ai.registry import load_registry
from person_search.services.searches import attributes_prompt


def _norm(values) -> float:
    return math.sqrt(sum(value * value for value in values))


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
    gateway = build_rasa_query_gateway(
        registry.encoder,
        artifact_root=args.artifact_root,
        runtime_settings=load_rasa_settings(args.settings),
        device=args.device,
    )
    container = av.open(args.video)
    frame = person = None
    query_bytes = io.BytesIO()
    try:
        frame = next(container.decode(video=0)).to_image().convert("RGB")
        person = frame.crop((816, 399, 1009, 888))
        person.save(query_bytes, format="PNG")
    finally:
        container.close()

    version = registry.encoder.version
    dimension = registry.encoder.dimension
    text = "a person wearing a light colored top and dark pants"
    prompt = attributes_prompt(
        {"upper_color": "white", "lower_color": "black", "has_backpack": False}
    )
    gateway.open()
    try:
        image_vector = gateway.image(
            query_bytes.getvalue(), version=version, dimension=dimension
        )
        text_vector = gateway.text(text, version=version, dimension=dimension)
        attribute_vector = gateway.text(prompt, version=version, dimension=dimension)
    finally:
        gateway.close()
        query_bytes.close()
        person.close()
        frame.close()
    print(
        json.dumps(
            {
                "status": "ok",
                "dimension": dimension,
                "encoder_version": version,
                "image_norm": _norm(image_vector),
                "text_norm": _norm(text_vector),
                "attribute_norm": _norm(attribute_vector),
                "attribute_prompt": prompt,
                "rerank_enabled": False,
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
