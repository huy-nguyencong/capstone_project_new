"""Check the text-search path on RaSa's own domain: CUHK-PEDES person crops with their captions.

The purpose is to separate an implementation fault from a domain gap. The images and captions
go through exactly the adapters the application uses for queries (``build_rasa_query_gateway``:
image bytes -> ``gateway.image``, English sentence -> ``gateway.text``) and are ranked by inner
product as the vector search does. If the adapters were wrong, retrieval here would be close to
random; if they are right, it is close to the published figures of the checkpoint.

Data: the parquet shards of the Hugging Face copy ``MaulikMadhavi/CUHK-PEDES-processed``
(columns ``image``, ``text`` as a list of captions, ``filename``), which hold the training split
only; the published CUHK-PEDES test split is not redistributed. The identity of an image is read
from its file name (CUHK-PEDES keeps the naming of its five source datasets), so a caption
retrieving another image of the same person also counts as correct; in this copy the images of
one person share the same caption, so the identity-level figures are the meaningful ones.
Requires ``pyarrow``.

    python tools/rasa_domain_sanity.py --shards var/datasets/cuhk_pedes_processed/data \
        --registry config/models.example.json --artifact-root config \
        --settings config/rasa_cuhk_pedes_runtime.json --images 600 \
        --output var/evaluation/rasa-domain-sanity.json
"""

from __future__ import annotations

import argparse
import io
import json
import random
import re
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

from person_search.ai.encoders import build_rasa_query_gateway, load_rasa_settings
from person_search.ai.registry import load_registry
from person_search.evaluation.environment import environment_snapshot
from person_search.evaluation.metrics import wilson_interval

KS = (1, 5, 10)


IDENTITY_PATTERNS = (
    ("Market", re.compile(r"^(\d{4})_c\d+s\d+_\d+_\d+$")),  # 0002_c1s1_000451_03
    ("CUHK03", re.compile(r"^(\d+_\d{3})_\d+_\d+$")),  # 1_001_1_01: camera pair 1, person 001
    ("CUHK01", re.compile(r"^(\d{4})\d{3}$")),  # 0363004: person 0363, shot 004
    ("SSM", re.compile(r"^(p\d+)_s\d+$")),  # p10376_s14337
    ("VIPER", re.compile(r"^(\d{3})_\d+$")),  # 000_45: person 000
)


def identity_of(filename: str) -> str:
    """Person identity encoded in a CUHK-PEDES file name (the copy keeps no directory)."""

    stem = filename.replace("\\", "/").rsplit("/", 1)[-1].rsplit(".", 1)[0]
    for source, pattern in IDENTITY_PATTERNS:
        match = pattern.match(stem)
        if match:
            return f"{source}/{match.group(1)}"
    return f"unknown/{stem}"


def load_rows(shards: Path, images: int, seed: int) -> list[dict]:
    import pyarrow.parquet as pq

    rows = []
    for shard in sorted(shards.glob("*.parquet")):
        table = pq.read_table(shard, columns=["image", "text", "filename"])
        for record in table.to_pylist():
            captions = [c for c in (record["text"] or []) if isinstance(c, str) and c.strip()]
            if not captions:
                continue
            rows.append(
                {
                    "filename": record["filename"],
                    "identity": identity_of(record["filename"]),
                    "caption": captions[0],
                    "captions": len(captions),
                    "image_bytes": record["image"]["bytes"],
                }
            )
    random.Random(seed).shuffle(rows)
    return rows[:images]


def itm_check(rows, *, queries, top_k, registry_path, artifact_root, settings_path) -> dict:
    """Contrastive-only against ITM re-ranked retrieval, as in the upstream ``evaluation()``."""

    import torch
    from PIL import Image

    from person_search.ai.encoders import RasaRuntimeFactory
    from person_search.ai.encoders.rasa_vendor.tokenization_bert import BertTokenizer

    registry = load_registry(
        registry_path, artifact_root=artifact_root, preflight_available={"rasa_cuhk_pedes_v1"}
    )
    factory = RasaRuntimeFactory(
        registry.encoder, artifact_root=artifact_root, settings=load_rasa_settings(settings_path)
    )
    runtime = factory.load(full_training_module=True)  # fusion layers and itm_head are needed
    model = runtime.model
    tokenizer = BertTokenizer(vocab_file=str(factory.vocab), do_lower_case=True)
    identities = [row["identity"] for row in rows]
    started = time.perf_counter()
    feats, embeds = [], []
    with torch.inference_mode():
        for row in rows:
            with Image.open(io.BytesIO(row["image_bytes"])) as opened:
                tensor = runtime.preprocessor.image(opened.convert("RGB")).unsqueeze(0)
            feat = model.visual_encoder(tensor)
            feats.append(feat)
            embeds.append(torch.nn.functional.normalize(model.vision_proj(feat[:, 0, :]), dim=-1))
        feats, embeds = torch.cat(feats), torch.cat(embeds)
        itc_ranks, itm_ranks = [], []
        for row in rows[:queries]:
            tokens = tokenizer(
                row["caption"],
                padding="max_length",
                truncation=True,
                max_length=50,
                return_tensors="pt",
            )
            text_out = model.text_encoder.bert(
                tokens.input_ids,
                attention_mask=tokens.attention_mask,
                return_dict=True,
                mode="text",
            )
            text_feat = text_out.last_hidden_state
            text_embed = torch.nn.functional.normalize(model.text_proj(text_feat[:, 0, :]), dim=-1)
            sims = (text_embed @ embeds.T)[0]
            order = sims.argsort(descending=True).tolist()
            itc_ranks.append(
                next(k for k, j in enumerate(order, 1) if identities[j] == row["identity"])
            )
            top = sims.topk(min(top_k, len(rows))).indices
            fusion = model.text_encoder.bert(
                encoder_embeds=text_feat.repeat(len(top), 1, 1),
                attention_mask=tokens.attention_mask.repeat(len(top), 1),
                encoder_hidden_states=feats[top],
                encoder_attention_mask=torch.ones(feats[top].shape[:-1], dtype=torch.long),
                return_dict=True,
                mode="fusion",
            )
            score = model.itm_head(fusion.last_hidden_state[:, 0, :])[:, 1]
            scores = torch.full((len(rows),), -100.0)
            scores[top] = score
            order = scores.argsort(descending=True).tolist()
            itm_ranks.append(
                next(k for k, j in enumerate(order, 1) if identities[j] == row["identity"])
            )

    def summary(ranks):
        n = len(ranks)
        out = {"n": n, "median_rank": sorted(ranks)[n // 2]}
        for k in KS:
            hits = sum(1 for r in ranks if r <= k)
            out[f"recall@{k}"] = round(hits / n, 4)
            out[f"recall@{k}_ci95"] = wilson_interval(hits, n)
        return out

    result = {
        "gallery_images": len(rows),
        "queries": queries,
        "top_k": top_k,
        "contrastive_only": summary(itc_ranks),
        "itm_reranked": summary(itm_ranks),
        "elapsed_seconds": round(time.perf_counter() - started, 1),
    }
    for label in ("contrastive_only", "itm_reranked"):
        print(f"itm check {label}: " + json.dumps(result[label]))
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--shards", type=Path, required=True)
    parser.add_argument("--registry", required=True)
    parser.add_argument("--artifact-root", required=True)
    parser.add_argument("--settings", required=True)
    parser.add_argument("--images", type=int, default=600)
    parser.add_argument("--seed", type=int, default=20261005)
    parser.add_argument(
        "--itm-queries",
        type=int,
        default=0,
        help="also re-rank this many captions with the ITM head over the first --itm-gallery "
        "images, as the upstream evaluation does (needs the fusion layers; slow on a CPU)",
    )
    parser.add_argument("--itm-gallery", type=int, default=150)
    parser.add_argument("--itm-top-k", type=int, default=32)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    rows = load_rows(args.shards, args.images, args.seed)
    identities = {row["identity"] for row in rows}
    print(f"{len(rows)} images, {len(identities)} identities, first caption of each image")

    registry = load_registry(
        args.registry, artifact_root=args.artifact_root, preflight_available={"rasa_cuhk_pedes_v1"}
    )
    assert registry.encoder is not None
    encoder = registry.encoder
    gateway = build_rasa_query_gateway(
        encoder,
        artifact_root=args.artifact_root,
        runtime_settings=load_rasa_settings(args.settings),
    )
    gateway.open()
    started = time.perf_counter()
    try:
        # Image bytes are re-encoded as PNG so that the gateway's validation sees a normal upload.
        from PIL import Image

        image_vectors = []
        for index, row in enumerate(rows):
            with Image.open(io.BytesIO(row["image_bytes"])) as opened:
                buffer = io.BytesIO()
                opened.convert("RGB").save(buffer, format="PNG")
            image_vectors.append(
                gateway.image(
                    buffer.getvalue(), version=encoder.version, dimension=encoder.dimension
                )
            )
            if (index + 1) % 100 == 0:
                print(f"  encoded {index + 1} images in {time.perf_counter() - started:.0f} s")
        text_vectors = [
            gateway.text(row["caption"], version=encoder.version, dimension=encoder.dimension)
            for row in rows
        ]
    finally:
        gateway.close()
    elapsed = time.perf_counter() - started

    import torch

    images = torch.tensor(image_vectors)
    texts = torch.tensor(text_vectors)
    scores = texts @ images.T  # caption i against every image
    order = scores.argsort(dim=1, descending=True)
    first_same_image, first_same_identity = [], []
    for i, row in enumerate(rows):
        ranked = order[i].tolist()
        first_same_image.append(ranked.index(i) + 1)
        first_same_identity.append(
            next(
                rank
                for rank, j in enumerate(ranked, start=1)
                if rows[j]["identity"] == row["identity"]
            )
        )

    # Image-to-image on the same sample: a query image against the other images, correct when the
    # same identity comes first; shows whether the visual side alone separates identities.
    image_scores = images @ images.T
    image_scores.fill_diagonal_(-2.0)
    image_order = image_scores.argsort(dim=1, descending=True)
    first_same_identity_image = []
    for i, row in enumerate(rows):
        others = [j for j in range(len(rows)) if j != i and rows[j]["identity"] == row["identity"]]
        if not others:
            continue
        ranked = image_order[i].tolist()
        first_same_identity_image.append(
            next(rank for rank, j in enumerate(ranked, start=1) if j in others)
        )
    positive_cosine = [float(scores[i, i]) for i in range(len(rows))]
    off = scores.clone()
    off.fill_diagonal_(float("nan"))
    negative_cosine = off[~off.isnan()]

    def summary(ranks):
        n = len(ranks)
        out = {
            "n": n,
            "median_rank": sorted(ranks)[n // 2],
            "mrr": round(sum(1 / r for r in ranks) / n, 4),
        }
        for k in KS:
            hits = sum(1 for r in ranks if r <= k)
            out[f"recall@{k}"] = round(hits / n, 4)
            out[f"recall@{k}_ci95"] = wilson_interval(hits, n)
        return out

    itm = None
    if args.itm_queries > 0:
        itm = itm_check(
            rows[: args.itm_gallery],
            queries=args.itm_queries,
            top_k=args.itm_top_k,
            registry_path=args.registry,
            artifact_root=args.artifact_root,
            settings_path=args.settings,
        )

    report = {
        "schema": "person-search-rasa-domain-sanity/v1",
        "measured_at": datetime.now(UTC).isoformat(),
        "python": sys.version.split()[0],
        "data": {
            "source": "huggingface.co/datasets/MaulikMadhavi/CUHK-PEDES-processed"
            " (training split of CUHK-PEDES)",
            "shards": sorted(p.name for p in args.shards.glob("*.parquet")),
            "images": len(rows),
            "identities": len(identities),
            "seed": args.seed,
            "caption_policy": "first caption of each image; gallery = the sampled images",
        },
        "encoder": {
            "id": encoder.id,
            "version": encoder.version,
            "sha256": encoder.artifact.sha256,
        },
        "path": "build_rasa_query_gateway: gateway.image(PNG bytes) and gateway.text(sentence),"
        " inner product ranking",
        "text_to_image": {
            "same_image": summary(first_same_image),
            "same_identity": summary(first_same_identity),
            "paired_cosine_mean": round(sum(positive_cosine) / len(positive_cosine), 4),
            "unpaired_cosine_mean": round(float(negative_cosine.mean()), 4),
            "unpaired_cosine_std": round(float(negative_cosine.std()), 4),
            "random_expectation": {
                "recall@1": round(1 / len(rows), 4),
                "recall@10": round(10 / len(rows), 4),
            },
        },
        "image_to_image": {
            "same_identity": summary(first_same_identity_image),
            "note": "query image against the other sampled images; only identities with 2+ images",
        },
        "vectors": {
            "filenames": [row["filename"] for row in rows],
            "identities": [row["identity"] for row in rows],
            "captions": [row["caption"] for row in rows],
            "image": [[round(v, 6) for v in vec] for vec in image_vectors],
            "text": [[round(v, 6) for v in vec] for vec in text_vectors],
        },
        "itm_rerank_check": itm,
        "published_reference": {
            "note": "RaSa on the CUHK-PEDES test split (Bai et al., IJCAI 2023): Rank-1 76.51,"
            " Rank-5 90.15, Rank-10 94.25, mAP 69.38; a sample of the training split is expected"
            " to score at least as high",
        },
        "elapsed_seconds": round(elapsed, 1),
        "environment": environment_snapshot(),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    for label in ("same_image", "same_identity"):
        s = report["text_to_image"][label]
        print(f"text->image {label}: " + json.dumps(s))
    for label in ("image_to_image",):
        s = report[label]["same_identity"]
        print(
            f"{label:14s} R@1 {s['recall@1']:.3f} R@5 {s['recall@5']:.3f} R@10 {s['recall@10']:.3f}"
            f" MRR {s['mrr']:.3f} median rank {s['median_rank']} (n={s['n']})"
        )
    print(f"written {args.output} ({elapsed:.0f} s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
