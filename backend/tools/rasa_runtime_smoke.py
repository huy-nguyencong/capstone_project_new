"""Load the pinned RaSa checkpoint and produce real image/text embeddings."""

from __future__ import annotations

import argparse
import json

import av

from person_search.ai.encoders import RasaRuntimeFactory, load_rasa_settings
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
    factory = RasaRuntimeFactory(
        registry.encoder,
        artifact_root=args.artifact_root,
        settings=load_rasa_settings(args.settings),
        device=args.device,
    )
    metadata = factory.inspect_checkpoint()
    runtime = factory.load()
    container = av.open(args.video)
    try:
        image = next(container.decode(video=0)).to_image().convert("RGB")
    finally:
        container.close()
    person = image.crop((816, 399, 1009, 888))
    try:
        image_vector = runtime.image_embedding(person).detach().cpu()
        repeated_image_vector = runtime.image_embedding(person).detach().cpu()
        text_vector = runtime.text_embedding(
            "a person wearing dark trousers and a light colored top"
        ).detach().cpu()
        repeated_text_vector = runtime.text_embedding(
            "a person wearing dark trousers and a light colored top"
        ).detach().cpu()
    finally:
        person.close()
        image.close()
    cosine = float((image_vector @ text_vector.T).item())
    print(
        json.dumps(
            {
                "status": "ok",
                "state_keys": metadata.state_keys,
                "dimension": image_vector.shape[1],
                "image_norm": float(image_vector.norm().item()),
                "text_norm": float(text_vector.norm().item()),
                "image_text_cosine": cosine,
                "image_repeat_max_delta": float(
                    (image_vector - repeated_image_vector).abs().max().item()
                ),
                "text_repeat_max_delta": float(
                    (text_vector - repeated_text_vector).abs().max().item()
                ),
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
