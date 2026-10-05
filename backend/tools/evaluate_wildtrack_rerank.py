"""Text and attribute search on WILDTRACK with RaSa's ITM re-ranking over the vector candidates.

Uses the gallery cache written by ``evaluate_wildtrack.py --gallery-cache`` (tracks with their
representative boxes and contrastive embeddings) and the same query file. For every text and
attribute query: the contrastive vector ranks the whole gallery (as the application's vector
search does), the top ``--pools`` candidates are re-ranked with the image-text matching head
(as the authors' evaluation does over the top 128), and Recall@k and MRR are reported for the
vector ranking and for each pool size. The image token features of every gallery track are
computed once (about 1.3 s per track on the CPU) and kept in ``--token-cache`` as float16.

    python tools/evaluate_wildtrack_rerank.py --dataset-root ../wildtrack-dataset \
        --queries ../files/wildtrack_evaluation_queries_v2.json \
        --gallery-cache var/evaluation/wildtrack-gallery-conf010.json \
        --token-cache var/evaluation/wildtrack-gallery-conf010-tokens.npy \
        --registry config/models.example.json --artifact-root config \
        --settings config/rasa_cuhk_pedes_runtime.json --pools 16,32,64,128 \
        --output var/evaluation/wildtrack-v2-conf010-rerank.json
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

from person_search.ai.encoders import RasaRuntimeFactory, load_rasa_settings
from person_search.ai.registry import load_registry
from person_search.evaluation.environment import environment_snapshot
from person_search.evaluation.metrics import RECALL_KS, wilson_interval
from person_search.services.searches import attributes_prompt


def load_gallery(path: Path) -> list[dict]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    items = []
    for run in payload["runs"]:
        for item in run["gallery"]:
            items.append(item)
    return items


def gallery_tokens(items, runtime, dataset_root: Path, cache: Path):
    import numpy as np
    import torch
    from PIL import Image

    if cache.is_file():
        tokens = np.load(cache, mmap_mode="r")
        if tokens.shape[0] == len(items):
            print(f"token cache {cache}: {tokens.shape}")
            return torch.from_numpy(np.ascontiguousarray(tokens))
        print("token cache has another gallery size; recomputing")
    tokens = np.zeros((len(items), 577, 768), dtype=np.float16)
    started = time.perf_counter()
    for index, item in enumerate(items):
        frame = dataset_root / "Image_subsets" / item["camera"] / f"{item['frame']:08d}.png"
        x1, y1, x2, y2 = item["box"]
        with Image.open(frame) as opened:
            crop = opened.convert("RGB").crop((round(x1), round(y1), round(x2), round(y2)))
        tokens[index] = runtime.image_tokens(crop)[0].cpu().numpy().astype(np.float16)
        if (index + 1) % 100 == 0:
            print(
                f"  tokens for {index + 1} tracks in {time.perf_counter() - started:.0f} s",
                flush=True,
            )
    cache.parent.mkdir(parents=True, exist_ok=True)
    np.save(cache, tokens)
    print(f"token cache written: {cache} in {time.perf_counter() - started:.0f} s")
    return torch.from_numpy(tokens)


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


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--dataset-root", type=Path, required=True)
    parser.add_argument("--queries", type=Path, required=True)
    parser.add_argument("--gallery-cache", type=Path, required=True)
    parser.add_argument("--token-cache", type=Path, required=True)
    parser.add_argument("--registry", required=True)
    parser.add_argument("--artifact-root", required=True)
    parser.add_argument("--settings", required=True)
    parser.add_argument("--pools", default="16,32,64,128")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    pools = sorted({int(p) for p in args.pools.split(",") if p.strip()})

    import torch

    items = load_gallery(args.gallery_cache)
    embeddings = torch.tensor([item["embedding"] for item in items])
    person_ids = [item["person_id"] for item in items]
    queries = json.loads(args.queries.read_text(encoding="utf-8"))["queries"]

    registry = load_registry(
        args.registry, artifact_root=args.artifact_root, preflight_available={"rasa_cuhk_pedes_v1"}
    )
    assert registry.encoder is not None
    runtime = RasaRuntimeFactory(
        registry.encoder,
        artifact_root=args.artifact_root,
        settings=load_rasa_settings(args.settings),
        keep_fusion_layers=True,
    ).load()
    tokens = gallery_tokens(items, runtime, args.dataset_root, args.token_cache)

    results = {}
    per_query = []
    started = time.perf_counter()
    itm_seconds = 0.0
    itm_candidates = 0
    for mode in ("text", "attribute"):
        ranks = {"vector": []}
        for pool in pools:
            ranks[f"itm@{pool}"] = []
        for query in queries:
            sentence = (
                query["text_query"]
                if mode == "text"
                else attributes_prompt(query["attribute_query"])
            )
            person = int(query["person_id"])
            text_vector = runtime.text_embedding(sentence).cpu()[0]
            sims = embeddings @ text_vector
            order = sims.argsort(descending=True).tolist()
            positives = [j for j in order if person_ids[j] == person]
            first = next((r for r, j in enumerate(order, 1) if person_ids[j] == person), None)
            ranks["vector"].append(first if positives else None)
            row = {"query_id": query["id"], "mode": mode, "person_id": person, "vector_rank": first}
            largest = max(pools)
            top = order[:largest]
            t0 = time.perf_counter()
            scores_top = runtime.itm_scores(sentence, tokens[top]).cpu()
            itm_seconds += time.perf_counter() - t0
            itm_candidates += len(top)
            for pool in pools:
                subset = top[:pool]
                sub_scores = scores_top[:pool]
                reordered = [subset[i] for i in sub_scores.argsort(descending=True).tolist()]
                rest = order[pool:]
                final = reordered + rest
                first_itm = next(
                    (r for r, j in enumerate(final, 1) if person_ids[j] == person), None
                )
                ranks[f"itm@{pool}"].append(first_itm if positives else None)
                row[f"itm@{pool}_rank"] = first_itm
            per_query.append(row)
            print(json.dumps(row), flush=True)
        results[mode] = {label: summary(values) for label, values in ranks.items()}

    report = {
        "schema": "person-search-wildtrack-rerank-evaluation/v1",
        "measured_at": datetime.now(UTC).isoformat(),
        "python": sys.version.split()[0],
        "gallery": {"tracks": len(items), "cache": str(args.gallery_cache)},
        "queries": {"file": str(args.queries), "count": len(queries)},
        "pools": pools,
        "encoder": {
            "id": registry.encoder.id,
            "version": registry.encoder.version,
            "sha256": registry.encoder.artifact.sha256,
            "fusion_layers": True,
        },
        "timing": {
            "itm_seconds_per_candidate": round(itm_seconds / max(1, itm_candidates), 4),
            "itm_candidates": itm_candidates,
            "elapsed_seconds": round(time.perf_counter() - started, 1),
        },
        "retrieval": results,
        "per_query": per_query,
        "environment": environment_snapshot(),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    for mode, table in results.items():
        for label, s in table.items():
            print(
                f"{mode:9s} {label:8s} R@4 {s['recall@4']} R@8 {s['recall@8']}"
                f" R@16 {s['recall@16']}"
                f" MRR {s['mean_reciprocal_rank']} median {s['median_first_positive_rank']}"
            )
    print(f"written {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
