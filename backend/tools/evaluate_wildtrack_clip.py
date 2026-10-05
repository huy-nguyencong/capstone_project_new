"""Image, text and attribute search on WILDTRACK with a CLIP encoder instead of RaSa.

Evaluation only: the detection, tracking and representative frames come from the gallery cache
written by ``evaluate_wildtrack.py --gallery-cache`` (the production pipeline), so only the
encoder changes. Every representative crop is re-encoded with an open_clip model, the queries of
the evaluation file are encoded the same way (crop, sentence, attribute sentence from the
application's template) and ranked by cosine exactly as ``evaluate_wildtrack.py`` ranks them
(the query's own observation excluded). Gallery embeddings are cached per model.

    python tools/evaluate_wildtrack_clip.py --dataset-root ../wildtrack-dataset \
        --queries ../files/wildtrack_evaluation_queries_v2.json \
        --gallery-cache var/evaluation/wildtrack-gallery-conf010.json \
        --model ViT-B-16 --pretrained laion2b_s34b_b88k \
        --embedding-cache var/evaluation/wildtrack-clip-vit-b16-embeddings.json \
        --output var/evaluation/wildtrack-v2-conf010-clip-vit-b16.json
"""

from __future__ import annotations

import argparse
import io
import json
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

from PIL import Image

from person_search.evaluation.environment import environment_snapshot
from person_search.evaluation.metrics import Box, GalleryItem, rank_gallery, recall_summary
from person_search.evaluation.wildtrack_eval import query_crop_png
from person_search.services.searches import attributes_prompt

PREFIXES = {"raw": "", "photo": "a photo of "}


def crop(dataset_root: Path, camera: str, frame: int, box: Box) -> Image.Image:
    path = dataset_root / "Image_subsets" / camera / f"{frame:08d}.png"
    with Image.open(path) as opened:
        return opened.convert("RGB").crop(
            (round(box.x1), round(box.y1), round(box.x2), round(box.y2))
        )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--dataset-root", type=Path, required=True)
    parser.add_argument("--queries", type=Path, required=True)
    parser.add_argument("--gallery-cache", type=Path, required=True)
    parser.add_argument("--model", default="ViT-B-16")
    parser.add_argument("--pretrained", default="laion2b_s34b_b88k")
    parser.add_argument("--weights-dir", type=Path, default=Path("var/datasets/open_clip"))
    parser.add_argument("--embedding-cache", type=Path, required=True)
    parser.add_argument("--batch-size", type=int, default=16)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    import open_clip
    import torch

    model, _, preprocess = open_clip.create_model_and_transforms(
        args.model, pretrained=args.pretrained, cache_dir=str(args.weights_dir)
    )
    tokenizer = open_clip.get_tokenizer(args.model)
    model.eval()

    def encode_images(images):
        with torch.inference_mode():
            batch = torch.stack([preprocess(image) for image in images])
            vectors = model.encode_image(batch)
            return torch.nn.functional.normalize(vectors, dim=-1).tolist()

    def encode_text(text):
        with torch.inference_mode():
            vectors = model.encode_text(tokenizer([text]))
            return torch.nn.functional.normalize(vectors, dim=-1)[0].tolist()

    payload = json.loads(args.gallery_cache.read_text(encoding="utf-8"))
    items = [item for run in payload["runs"] for item in run["gallery"]]
    cache = (
        json.loads(args.embedding_cache.read_text(encoding="utf-8"))
        if args.embedding_cache.is_file()
        else {}
    )
    tag = f"{args.model}:{args.pretrained}"
    store = cache.setdefault(tag, {})
    missing = [item for item in items if item["key"] not in store]
    started = time.perf_counter()
    for start in range(0, len(missing), args.batch_size):
        chunk = missing[start : start + args.batch_size]
        images = [crop(args.dataset_root, i["camera"], i["frame"], Box(*i["box"])) for i in chunk]
        try:
            for item, vector in zip(chunk, encode_images(images), strict=True):
                store[item["key"]] = vector
        finally:
            for image in images:
                image.close()
        done = start + len(chunk)
        if done % (args.batch_size * 10) == 0 or done == len(missing):
            print(
                f"  encoded {done}/{len(missing)} crops in {time.perf_counter() - started:.0f} s",
                flush=True,
            )
            args.embedding_cache.parent.mkdir(parents=True, exist_ok=True)
            args.embedding_cache.write_text(json.dumps(cache), encoding="utf-8")
    gallery_seconds = time.perf_counter() - started
    gallery = [
        GalleryItem(
            key=item["key"],
            person_id=item["person_id"],
            camera=item["camera"],
            frame=item["frame"],
            box=Box(*item["box"]),
            embedding=tuple(store[item["key"]]),
        )
        for item in items
    ]

    queries = json.loads(args.queries.read_text(encoding="utf-8"))["queries"]
    outcomes = {"image": [], "text": [], "attribute": []}
    for prefix in PREFIXES:
        outcomes[f"text_{prefix}"] = []
        outcomes[f"attribute_{prefix}"] = []
    for query in queries:
        image_query = query["image_query"]
        bbox = image_query["bbox"]
        exclude = (
            image_query["camera"],
            int(image_query["frame"]),
            Box.from_inclusive(bbox["xmin"], bbox["ymin"], bbox["xmax"], bbox["ymax"]),
        )
        person = int(query["person_id"])
        with Image.open(io.BytesIO(query_crop_png(args.dataset_root, image_query))) as image:
            image_vector = encode_images([image.convert("RGB")])[0]
        outcomes["image"].append(
            rank_gallery(query["id"], "image", person, image_vector, gallery, exclude=exclude)
        )
        sentences = {
            "text": query["text_query"],
            "attribute": attributes_prompt(query["attribute_query"]),
        }
        for mode, sentence in sentences.items():
            for prefix, words in PREFIXES.items():
                vector = encode_text(words + sentence)
                outcome = rank_gallery(
                    query["id"], f"{mode}_{prefix}", person, vector, gallery, exclude=exclude
                )
                outcomes[f"{mode}_{prefix}"].append(outcome)
                if prefix == "raw":
                    outcomes[mode].append(outcome)
    # Each list is summarised on its own: the "text"/"attribute" lists alias the raw-prefix runs.
    summary = {}
    for mode, rows in outcomes.items():
        if not rows:
            continue
        summary[mode] = next(iter(recall_summary(rows).values()))
        ranks = sorted(o.first_positive_rank for o in rows if o.first_positive_rank)
        summary[mode]["median_first_positive_rank"] = ranks[len(ranks) // 2] if ranks else None

    report = {
        "schema": "person-search-wildtrack-clip-evaluation/v1",
        "measured_at": datetime.now(UTC).isoformat(),
        "python": sys.version.split()[0],
        "encoder": {"library": "open_clip", "model": args.model, "pretrained": args.pretrained},
        "gallery": {
            "tracks": len(gallery),
            "cache": str(args.gallery_cache),
            "encode_seconds": round(gallery_seconds, 1),
        },
        "queries": {"file": str(args.queries), "count": len(queries)},
        "prefixes": PREFIXES,
        "retrieval": summary,
        "per_query": [o.as_dict() for rows in outcomes.values() for o in rows],
        "environment": environment_snapshot(),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    for mode in ("image", "text", "attribute", "text_photo", "attribute_photo"):
        s = summary[mode]
        print(
            f"{mode:16s} R@4 {s['recall@4']} R@8 {s['recall@8']} R@16 {s['recall@16']}"
            f" MRR {s['mean_reciprocal_rank']} median {s['median_first_positive_rank']}"
        )
    print(f"written {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
