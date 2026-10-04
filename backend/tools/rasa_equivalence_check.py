"""Check that the inference-only RaSa module produces the same vectors as the training-time module.

Two child processes load the same checkpoint, one through the original ``ALBEF`` class
(``full_training_module=True``) and one through ``RasaInferenceModel`` (the production path), and
embed the same person crops from WILDTRACK and the same English sentences. The parent compares the
vectors element-wise. A pass means the vector space is unchanged, so the Milvus collection and the
encoder version stay as they are (NFR-09). Each child also reports its resident memory after the
embeddings, which gives the steady-state figure of both paths in one run.

    python tools/rasa_equivalence_check.py --registry config/models.example.json \
        --artifact-root config --settings config/rasa_cuhk_pedes_runtime.json \
        --dataset-root ../wildtrack-dataset --queries ../files/wildtrack_evaluation_queries.json \
        --output var/benchmark/rasa-equivalence.json
"""

from __future__ import annotations

import argparse
import json
import multiprocessing
import sys
import time
from datetime import UTC, datetime
from multiprocessing.connection import Connection
from pathlib import Path

ATOL = 1e-6
EXTRA_SENTENCES = (
    "a person wearing dark trousers and a light colored top",
    "A woman wearing a red jacket and blue jeans, carrying a handbag.",
    "A man in a white shirt and black shorts with a backpack.",
    "a person wearing a yellow top",
)


def _crops(dataset_root: Path, limit: int) -> list[dict]:
    """Person boxes from the first annotated frames, spread over the seven cameras."""

    crops: list[dict] = []
    for annotation in sorted((dataset_root / "annotations_positions").glob("*.json")):
        frame = annotation.stem
        for person in json.loads(annotation.read_text(encoding="utf-8")):
            for view in person["views"]:
                if view["xmin"] < 0:
                    continue
                width = view["xmax"] - view["xmin"] + 1
                height = view["ymax"] - view["ymin"] + 1
                if width < 24 or height < 48:
                    continue
                crops.append(
                    {
                        "camera": f"C{view['viewNum'] + 1}",
                        "frame": frame,
                        "person_id": person["personID"],
                        "box": [view["xmin"], view["ymin"], view["xmax"] + 1, view["ymax"] + 1],
                    }
                )
                if len(crops) >= limit:
                    return crops
    return crops


def _sentences(queries_path: Path | None) -> list[str]:
    sentences = list(EXTRA_SENTENCES)
    if queries_path is not None:
        payload = json.loads(queries_path.read_text(encoding="utf-8"))
        sentences.extend(query["text_query"] for query in payload["queries"])
    return sentences


def _child(
    connection: Connection,
    *,
    registry_path: str,
    artifact_root: str,
    settings_path: str,
    dataset_root: str,
    crops: list[dict],
    sentences: list[str],
    full_training_module: bool,
) -> None:
    try:
        import psutil
        from PIL import Image

        from person_search.ai.encoders import RasaRuntimeFactory, load_rasa_settings
        from person_search.ai.registry import load_registry

        registry = load_registry(
            registry_path,
            artifact_root=artifact_root,
            preflight_available={"rasa_cuhk_pedes_v1"},
        )
        assert registry.encoder is not None
        factory = RasaRuntimeFactory(
            registry.encoder,
            artifact_root=artifact_root,
            settings=load_rasa_settings(settings_path),
            device="cpu",
        )
        started = time.perf_counter()
        runtime = factory.load(full_training_module=full_training_module)
        load_seconds = time.perf_counter() - started
        image_vectors = []
        started = time.perf_counter()
        for crop in crops:
            path = Path(dataset_root) / "Image_subsets" / crop["camera"] / f"{crop['frame']}.png"
            with Image.open(path) as frame:
                person = frame.crop(tuple(crop["box"]))
            try:
                image_vectors.append(runtime.image_embedding(person).reshape(-1).tolist())
            finally:
                person.close()
        image_seconds = time.perf_counter() - started
        started = time.perf_counter()
        text_vectors = [
            runtime.text_embedding(sentence).reshape(-1).tolist() for sentence in sentences
        ]
        text_seconds = time.perf_counter() - started
        info = psutil.Process().memory_info()
        connection.send(
            (
                "ok",
                {
                    "image_vectors": image_vectors,
                    "text_vectors": text_vectors,
                    "load_seconds": round(load_seconds, 2),
                    "image_seconds_per_crop": round(image_seconds / max(1, len(crops)), 3),
                    "text_seconds_per_sentence": round(text_seconds / max(1, len(sentences)), 3),
                    "rss_bytes": info.rss,
                    "peak_wset_bytes": int(getattr(info, "peak_wset", 0) or 0),
                    "fusion_layers_loaded": runtime.fusion_layers_loaded,
                },
            )
        )
    except BaseException as error:
        connection.send(("error", f"{type(error).__name__}: {error}"))
    finally:
        connection.close()


def _run(label: str, **kwargs) -> dict:
    context = multiprocessing.get_context("spawn")
    parent, child = context.Pipe()
    process = context.Process(target=_child, args=(child,), kwargs=kwargs, daemon=True)
    process.start()
    child.close()
    try:
        if not parent.poll(1800):
            raise TimeoutError(f"{label}: no result after 1800 seconds")
        status, payload = parent.recv()
    finally:
        parent.close()
        process.join(timeout=30)
        if process.is_alive():
            process.kill()
            process.join()
    if status != "ok":
        raise RuntimeError(f"{label}: {payload}")
    mib = 2**20
    print(
        f"  {label:18s} load {payload['load_seconds']:6.1f}s"
        f"  image {payload['image_seconds_per_crop']:.3f}s/crop"
        f"  text {payload['text_seconds_per_sentence']:.3f}s/sentence"
        f"  rss {payload['rss_bytes'] / mib:6.0f} MiB"
        f"  peak {payload['peak_wset_bytes'] / mib:6.0f} MiB"
    )
    return payload


def _compare(reference: list[list[float]], candidate: list[list[float]]) -> dict:
    import torch

    a = torch.tensor(reference, dtype=torch.float64)
    b = torch.tensor(candidate, dtype=torch.float64)
    diff = (a - b).abs()
    cosine = (a * b).sum(dim=1) / (a.norm(dim=1) * b.norm(dim=1))
    return {
        "count": int(a.shape[0]),
        "max_abs_diff": float(diff.max()) if a.numel() else 0.0,
        "mean_abs_diff": float(diff.mean()) if a.numel() else 0.0,
        "min_cosine": float(cosine.min()) if a.numel() else 1.0,
        "all_close": bool(torch.allclose(a, b, atol=ATOL, rtol=0.0)),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--registry", required=True)
    parser.add_argument("--artifact-root", required=True)
    parser.add_argument("--settings", required=True)
    parser.add_argument("--dataset-root", type=Path, required=True)
    parser.add_argument(
        "--queries", type=Path, help="evaluation query file; its sentences are added"
    )
    parser.add_argument("--crops", type=int, default=50)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    crops = _crops(args.dataset_root, args.crops)
    sentences = _sentences(args.queries)
    print(f"{len(crops)} crops, {len(sentences)} sentences")
    common = {
        "registry_path": args.registry,
        "artifact_root": args.artifact_root,
        "settings_path": args.settings,
        "dataset_root": str(args.dataset_root),
        "crops": crops,
        "sentences": sentences,
    }
    reference = _run("training_module", full_training_module=True, **common)
    candidate = _run("inference_module", full_training_module=False, **common)
    image = _compare(reference["image_vectors"], candidate["image_vectors"])
    text = _compare(reference["text_vectors"], candidate["text_vectors"])
    passed = image["all_close"] and text["all_close"]
    report = {
        "schema": "person-search-rasa-equivalence/v1",
        "measured_at": datetime.now(UTC).isoformat(),
        "python": sys.version.split()[0],
        "atol": ATOL,
        "passed": passed,
        "image": image,
        "text": text,
        "crops": crops,
        "sentences": sentences,
        "runs": {
            label: {key: value for key, value in run.items() if not key.endswith("_vectors")}
            for label, run in (("training_module", reference), ("inference_module", candidate))
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(
        f"image: max |diff| {image['max_abs_diff']:.2e}, min cosine {image['min_cosine']:.8f};"
        f" text: max |diff| {text['max_abs_diff']:.2e}, min cosine {text['min_cosine']:.8f}"
    )
    print(("PASS" if passed else "FAIL") + f"  written {args.output}")
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
