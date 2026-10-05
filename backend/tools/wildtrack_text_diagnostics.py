"""Why text search fails on WILDTRACK: crop size, box tightness, frame choice, colour queries.

Everything starts from the gallery cache of ``evaluate_wildtrack.py`` (the pipeline's tracks with
their representative boxes and contrastive embeddings). Four diagnostics, vector search only:

1. **Crop size**: height, width and aspect of the pipeline crops against the 128x384 crops the
   encoder was trained on.
2. **Box tightness**: the same representative frames, but the person cut with the hand-drawn
   label box of the matched person instead of the detector box.
3. **Frame choice and tightness together**: a gallery of label crops, the tallest box of each
   person on each camera, for people with at least ``--min-observations`` labelled boxes.
4. **Colour queries**: single-attribute sentences ranked over the pipeline gallery, with the
   top-16 crops saved as a montage for inspection, plus cosine statistics of every query.

The text and attribute queries of the evaluation file are run on all three galleries. Embeddings
of the two label galleries are cached in ``--embedding-cache`` (about 1.3 s per crop otherwise).

    python tools/wildtrack_text_diagnostics.py --dataset-root ../wildtrack-dataset \
        --queries ../files/wildtrack_evaluation_queries_v2.json \
        --gallery-cache var/evaluation/wildtrack-gallery-conf010.json \
        --embedding-cache var/evaluation/wildtrack-diag-embeddings.json \
        --registry config/models.example.json --artifact-root config \
        --settings config/rasa_cuhk_pedes_runtime.json \
        --montage-dir var/evaluation/color-queries \
        --output var/evaluation/wildtrack-text-diagnostics.json
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path

from PIL import Image, ImageDraw

from person_search.ai.encoders import RasaRuntimeFactory, load_rasa_settings
from person_search.ai.registry import load_registry
from person_search.evaluation.environment import environment_snapshot
from person_search.evaluation.metrics import RECALL_KS, Box, iou, wilson_interval
from person_search.evaluation.wildtrack_eval import CAMERAS, load_ground_truth
from person_search.services.searches import attributes_prompt

COLOR_QUERIES = (
    "A person wearing a red top.",
    "A person wearing a white top.",
    "A person wearing a black jacket.",
    "A person wearing blue jeans.",
    "A woman with a pink handbag.",
    "A man wearing a green jacket.",
)
FRAME_W, FRAME_H = 1920, 1080


def frame_path(dataset_root: Path, camera: str, frame: int) -> Path:
    return dataset_root / "Image_subsets" / camera / f"{frame:08d}.png"


def crop(dataset_root: Path, camera: str, frame: int, box: Box) -> Image.Image:
    with Image.open(frame_path(dataset_root, camera, frame)) as opened:
        return opened.convert("RGB").crop(
            (round(box.x1), round(box.y1), round(box.x2), round(box.y2))
        )


def box_key(kind: str, camera: str, frame: int, box: Box) -> str:
    return f"{kind}:{camera}:{frame}:{box.x1:.0f},{box.y1:.0f},{box.x2:.0f},{box.y2:.0f}"


def summary(ranks):
    evaluable = [r for r in ranks if r is not None]
    n = len(evaluable)
    out = {"queries": len(ranks), "evaluable_queries": n}
    for k in RECALL_KS:
        hits = sum(1 for r in evaluable if r <= k)
        out[f"recall@{k}"] = round(hits / n, 4) if n else None
        out[f"recall@{k}_ci95"] = wilson_interval(hits, n)
    out["mean_reciprocal_rank"] = round(sum(1 / r for r in evaluable) / n, 4) if n else None
    out["median_first_positive_rank"] = sorted(evaluable)[n // 2] if n else None
    return out


def rank_queries(queries, gallery, embeddings, runtime):
    """Text and attribute queries against one gallery; returns per-mode summaries and cosines."""

    import torch

    matrix = torch.tensor(embeddings)
    person_ids = [item["person_id"] for item in gallery]
    results, cosines = {}, {}
    for mode in ("text", "attribute"):
        ranks, stats = [], []
        for query in queries:
            sentence = (
                query["text_query"]
                if mode == "text"
                else attributes_prompt(query["attribute_query"])
            )
            vector = runtime.text_embedding(sentence).cpu()[0]
            sims = matrix @ vector
            order = sims.argsort(descending=True).tolist()
            person = int(query["person_id"])
            if not any(person_ids[j] == person for j in order):
                ranks.append(None)
            else:
                ranks.append(next(r for r, j in enumerate(order, 1) if person_ids[j] == person))
            sorted_sims = sims[order]
            stats.append(
                {
                    "query_id": query["id"],
                    "mean": round(float(sims.mean()), 4),
                    "std": round(float(sims.std()), 4),
                    "top1": round(float(sorted_sims[0]), 4),
                    "top16": round(float(sorted_sims[min(15, len(order) - 1)]), 4),
                    "top100": round(float(sorted_sims[min(99, len(order) - 1)]), 4),
                    "positives_mean": round(
                        float(
                            sims[[j for j in range(len(gallery)) if person_ids[j] == person]].mean()
                        ),
                        4,
                    )
                    if ranks[-1] is not None
                    else None,
                }
            )
        results[mode] = summary(ranks)
        results[mode]["per_query_first_rank"] = ranks
        cosines[mode] = stats
    return results, cosines


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--dataset-root", type=Path, required=True)
    parser.add_argument("--queries", type=Path, required=True)
    parser.add_argument("--gallery-cache", type=Path, required=True)
    parser.add_argument("--embedding-cache", type=Path, required=True)
    parser.add_argument("--registry", required=True)
    parser.add_argument("--artifact-root", required=True)
    parser.add_argument("--settings", required=True)
    parser.add_argument("--min-observations", type=int, default=30)
    parser.add_argument("--min-height", type=int, default=120)
    parser.add_argument("--montage-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    payload = json.loads(args.gallery_cache.read_text(encoding="utf-8"))
    pipeline = [item for run in payload["runs"] for item in run["gallery"]]
    queries = json.loads(args.queries.read_text(encoding="utf-8"))["queries"]
    truths = {camera: load_ground_truth(args.dataset_root, camera) for camera in CAMERAS}

    # ---- 1. crop size ----
    heights = [item["box"][3] - item["box"][1] for item in pipeline]
    widths = [item["box"][2] - item["box"][0] for item in pipeline]
    aspects = [w / h for w, h in zip(widths, heights, strict=True)]
    crop_size = {
        "tracks": len(pipeline),
        "height_px": {
            "median": round(statistics.median(heights), 1),
            "p10": round(sorted(heights)[len(heights) // 10], 1),
            "p90": round(sorted(heights)[len(heights) * 9 // 10], 1),
            "below_128": sum(1 for h in heights if h < 128),
            "below_384": sum(1 for h in heights if h < 384),
        },
        "width_px": {"median": round(statistics.median(widths), 1)},
        "aspect_w_over_h": {
            "median": round(statistics.median(aspects), 3),
            "training_crops": round(128 / 384, 3),
        },
        "labelled_tracks": sum(1 for item in pipeline if item["person_id"] is not None),
    }
    print(json.dumps({"crop_size": crop_size}))

    registry = load_registry(
        args.registry, artifact_root=args.artifact_root, preflight_available={"rasa_cuhk_pedes_v1"}
    )
    assert registry.encoder is not None
    runtime = RasaRuntimeFactory(
        registry.encoder,
        artifact_root=args.artifact_root,
        settings=load_rasa_settings(args.settings),
    ).load()

    cache = (
        json.loads(args.embedding_cache.read_text(encoding="utf-8"))
        if args.embedding_cache.is_file()
        else {}
    )

    def embed(key: str, image: Image.Image):
        if key not in cache:
            cache[key] = runtime.image_embedding(image).cpu()[0].tolist()
        return cache[key]

    def save_cache():
        args.embedding_cache.parent.mkdir(parents=True, exist_ok=True)
        args.embedding_cache.write_text(json.dumps(cache), encoding="utf-8")

    # ---- 2. same frames, label boxes ----
    tight, tight_embeddings, replaced = [], [], 0
    started = time.perf_counter()
    for index, item in enumerate(pipeline):
        box = Box(*item["box"])
        chosen = box
        if item["person_id"] is not None:
            candidates = [
                label_box
                for person, label_box in truths[item["camera"]].get(item["frame"], [])
                if person == item["person_id"]
            ]
            if candidates:
                chosen = max(candidates, key=lambda label_box: iou(label_box, box))
                replaced += 1
        key = box_key("tight", item["camera"], item["frame"], chosen)
        if key not in cache:
            image = crop(args.dataset_root, item["camera"], item["frame"], chosen)
            try:
                embed(key, image)
            finally:
                image.close()
        tight.append({**item, "box": [chosen.x1, chosen.y1, chosen.x2, chosen.y2]})
        tight_embeddings.append(cache[key])
        if (index + 1) % 100 == 0:
            print(
                f"  tight gallery {index + 1}/{len(pipeline)}"
                f" in {time.perf_counter() - started:.0f} s",
                flush=True,
            )
            save_cache()
    save_cache()
    print(f"tight gallery: {replaced} of {len(pipeline)} boxes replaced by label boxes")

    # ---- 3. label gallery: tallest inside-frame box per (person, camera) ----
    observations = defaultdict(int)
    best = {}
    for camera in CAMERAS:
        for frame, rows in truths[camera].items():
            for person, label_box in rows:
                observations[person] += 1
                inside = (
                    label_box.x1 >= 0
                    and label_box.y1 >= 0
                    and label_box.x2 <= FRAME_W
                    and label_box.y2 <= FRAME_H
                )
                height = label_box.y2 - label_box.y1
                if not inside or height < args.min_height:
                    continue
                key = (person, camera)
                if key not in best or height > best[key][1].y2 - best[key][1].y1:
                    best[key] = (frame, label_box)
    label_gallery, label_embeddings = [], []
    started = time.perf_counter()
    keys = sorted(key for key in best if observations[key[0]] >= args.min_observations)
    for index, (person, camera) in enumerate(keys):
        frame, label_box = best[(person, camera)]
        key = box_key("label", camera, frame, label_box)
        if key not in cache:
            image = crop(args.dataset_root, camera, frame, label_box)
            try:
                embed(key, image)
            finally:
                image.close()
        label_gallery.append(
            {
                "key": f"{camera}:{person}",
                "person_id": person,
                "camera": camera,
                "frame": frame,
                "box": [label_box.x1, label_box.y1, label_box.x2, label_box.y2],
            }
        )
        label_embeddings.append(cache[key])
        if (index + 1) % 100 == 0:
            print(
                f"  label gallery {index + 1}/{len(keys)} in {time.perf_counter() - started:.0f} s",
                flush=True,
            )
            save_cache()
    save_cache()
    print(f"label gallery: {len(label_gallery)} crops of {len({k[0] for k in keys})} people")

    # ---- queries on the three galleries ----
    galleries = {
        "pipeline_crops": (pipeline, [item["embedding"] for item in pipeline]),
        "same_frames_label_boxes": (tight, tight_embeddings),
        "label_gallery_best_box_per_person_camera": (label_gallery, label_embeddings),
    }
    retrieval, cosines = {}, {}
    for name, (gallery, embeddings) in galleries.items():
        retrieval[name], cosines[name] = rank_queries(queries, gallery, embeddings, runtime)
        for mode in ("text", "attribute"):
            s = retrieval[name][mode]
            print(
                f"{name:42s} {mode:9s} R@4 {s['recall@4']} R@8 {s['recall@8']}"
                f" R@16 {s['recall@16']}"
                f" MRR {s['mean_reciprocal_rank']} median {s['median_first_positive_rank']}"
                f" gallery {len(gallery)}"
            )

    # ---- 4. colour queries with montages on the pipeline gallery ----
    import torch

    args.montage_dir.mkdir(parents=True, exist_ok=True)
    matrix = torch.tensor([item["embedding"] for item in pipeline])
    color_results = []
    for sentence in COLOR_QUERIES:
        vector = runtime.text_embedding(sentence).cpu()[0]
        sims = matrix @ vector
        order = sims.argsort(descending=True).tolist()[:16]
        tiles = []
        for rank, j in enumerate(order, 1):
            item = pipeline[j]
            image = crop(args.dataset_root, item["camera"], item["frame"], Box(*item["box"]))
            tile = image.resize((max(40, int(image.width * 240 / image.height)), 240))
            image.close()
            draw = ImageDraw.Draw(tile)
            draw.rectangle((0, 0, tile.width - 1, 14), fill=(0, 0, 0))
            draw.text((2, 1), f"{rank} {float(sims[j]):.2f}", fill=(255, 255, 0))
            tiles.append(tile)
        width = sum(t.width for t in tiles) + 4 * len(tiles)
        sheet = Image.new("RGB", (width, 240), (255, 255, 255))
        x = 0
        for tile in tiles:
            sheet.paste(tile, (x, 0))
            x += tile.width + 4
        name = sentence.lower().strip(".").replace(" ", "_")
        path = args.montage_dir / f"{name}.png"
        sheet.save(path)
        color_results.append(
            {
                "query": sentence,
                "montage": str(path),
                "top16": [
                    {"key": pipeline[j]["key"], "score": round(float(sims[j]), 4)} for j in order
                ],
                "score_mean": round(float(sims.mean()), 4),
                "score_std": round(float(sims.std()), 4),
                "score_top1": round(float(sims[order[0]]), 4),
            }
        )
        print(f"colour query written: {path}")

    report = {
        "schema": "person-search-wildtrack-text-diagnostics/v1",
        "measured_at": datetime.now(UTC).isoformat(),
        "python": sys.version.split()[0],
        "gallery_cache": str(args.gallery_cache),
        "queries": {"file": str(args.queries), "count": len(queries)},
        "encoder": {"id": registry.encoder.id, "version": registry.encoder.version},
        "crop_size": crop_size,
        "galleries": {name: {"size": len(gallery)} for name, (gallery, _) in galleries.items()},
        "tight_boxes_replaced": replaced,
        "label_gallery_people": len({k[0] for k in keys}),
        "retrieval": retrieval,
        "cosine_by_query": cosines,
        "colour_queries": color_results,
        "environment": environment_snapshot(),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"written {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
