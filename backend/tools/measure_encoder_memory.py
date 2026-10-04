"""Measure how much memory each step of loading the RaSa encoder costs, step by step.

Two child processes are spawned one after the other, each reporting its own resident memory
(RSS, working set on Windows) and its peak working set after every step:

* ``stepwise`` repeats what ``RasaRuntimeFactory.load`` does, one step at a time: import torch,
  import the vendored model, construct the training-time ``ALBEF`` module (random weights),
  ``torch.load`` the checkpoint with ``mmap``, ``load_state_dict``, release the checkpoint, then
  one image and one text inference.
* ``production_path`` loads the encoder exactly through ``RasaRuntimeFactory.load`` and runs one
  inference, so the real steady-state and peak figures are measured as well.

The parent also sizes the checkpoint by top-level module and marks which modules inference uses.
Results for one ``--tag`` are written as JSON; a later tag (after a change) goes in another file.

    python tools/measure_encoder_memory.py --registry config/models.example.json \
        --artifact-root config --settings config/rasa_cuhk_pedes_runtime.json \
        --tag before --output var/benchmark/encoder-memory-before.json
"""

from __future__ import annotations

import argparse
import gc
import json
import multiprocessing
import platform
import sys
import time
from collections import OrderedDict
from datetime import UTC, datetime
from multiprocessing.connection import Connection
from pathlib import Path

# Modules of the checkpoint that the two inference paths (image_embedding, text_embedding) read.
INFERENCE_MODULES = {"visual_encoder", "text_encoder", "vision_proj", "text_proj"}
# The text path runs the BERT layers in ``mode="text"`` only; fusion layers and the MLM head are
# used by the (disabled) ITM re-ranking. They are reported separately inside ``text_encoder``.
TEXT_ENCODER_INFERENCE_PREFIXES = ("text_encoder.bert.embeddings.",)
TEXT_ENCODER_LAYER_PREFIX = "text_encoder.bert.encoder.layer."

MIB = 2**20


def _memory() -> dict[str, int]:
    import psutil

    info = psutil.Process().memory_info()
    return {"rss_bytes": info.rss, "peak_wset_bytes": int(getattr(info, "peak_wset", 0) or 0)}


class _Steps:
    def __init__(self, connection: Connection) -> None:
        self._connection = connection
        self._started = time.perf_counter()

    def mark(self, name: str) -> None:
        gc.collect()
        payload = _memory()
        payload["name"] = name
        payload["elapsed_seconds"] = round(time.perf_counter() - self._started, 3)
        self._connection.send(("step", payload))


def _sample_image():
    from PIL import Image

    # A person-sized synthetic crop; memory does not depend on the pixels.
    return Image.new("RGB", (193, 489), (120, 110, 100))


def _stepwise_child(connection: Connection, checkpoint: str, vendor_dir: str, vocab: str) -> None:
    steps = _Steps(connection)
    try:
        steps.mark("python_start")
        import torch

        steps.mark("import_torch")
        from person_search.ai.encoders.rasa_vendor.model_person_search import ALBEF

        steps.mark("import_vendored_model")
        # Same configuration as RasaRuntimeFactory.load (kept in sync by hand; measurement only).
        config = {
            "bert_config": str(Path(vendor_dir) / "config_bert.json"),
            "embed_dim": 256,
            "image_res": 384,
            "vision_width": 768,
            "temp": 0.07,
            "mlm_probability": 0.15,
            "mrtd_mask_probability": 0.3,
            "queue_size": 65536,
            "momentum": 0.995,
        }
        model = ALBEF(config=config, text_encoder=None, tokenizer=None)
        steps.mark("construct_albef_random_init")
        state = torch.load(checkpoint, map_location="cpu", weights_only=True, mmap=True)
        steps.mark("torch_load_mmap")
        model.load_state_dict(state["model"], strict=False)
        steps.mark("load_state_dict")
        del state
        steps.mark("release_checkpoint")
        model.eval()
        from torchvision.transforms import InterpolationMode
        from torchvision.transforms import functional as vision

        with torch.inference_mode():
            tensor = vision.normalize(
                vision.pil_to_tensor(
                    vision.resize(
                        _sample_image(), [384, 384], interpolation=InterpolationMode.BICUBIC
                    )
                )
                .to(dtype=torch.float32)
                .div_(255),
                [0.48145466, 0.4578275, 0.40821073],
                [0.26862954, 0.26130258, 0.27577711],
            ).unsqueeze(0)
            model.vision_proj(model.visual_encoder(tensor)[:, 0, :])
        steps.mark("image_inference")
        with torch.inference_mode():
            from transformers import BertTokenizer

            tokenizer = BertTokenizer(vocab_file=vocab, do_lower_case=True)
            tokens = tokenizer(
                "a person wearing dark trousers and a light colored top",
                padding="max_length",
                truncation=True,
                max_length=50,
                return_tensors="pt",
            )
            output = model.text_encoder.bert(
                tokens.input_ids,
                attention_mask=tokens.attention_mask,
                return_dict=True,
                mode="text",
            )
            model.text_proj(output.last_hidden_state[:, 0, :])
        steps.mark("text_inference")
        connection.send(("done", None))
    except BaseException as error:  # report, never hang the parent
        connection.send(("error", f"{type(error).__name__}: {error}"))
    finally:
        connection.close()


def _production_child(
    connection: Connection, registry_path: str, artifact_root: str, settings_path: str
) -> None:
    steps = _Steps(connection)
    try:
        steps.mark("python_start")
        from person_search.ai.encoders import RasaRuntimeFactory, load_rasa_settings
        from person_search.ai.registry import load_registry

        steps.mark("import_person_search")
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
        runtime = factory.load()
        steps.mark("factory_load")
        runtime.image_embedding(_sample_image())
        steps.mark("image_inference")
        runtime.text_embedding("a person wearing dark trousers and a light colored top")
        steps.mark("text_inference")
        for _ in range(5):
            runtime.image_embedding(_sample_image())
        steps.mark("five_more_image_inferences")
        connection.send(("done", None))
    except BaseException as error:
        connection.send(("error", f"{type(error).__name__}: {error}"))
    finally:
        connection.close()


def _run_child(target, args: tuple) -> dict:
    context = multiprocessing.get_context("spawn")
    parent, child = context.Pipe()
    process = context.Process(target=target, args=(child, *args), daemon=True)
    started = time.perf_counter()
    process.start()
    child.close()
    steps: list[dict] = []
    status, detail = "incomplete", None
    try:
        while True:
            if not parent.poll(900):
                status, detail = "timeout", "no message for 900 seconds"
                break
            kind, payload = parent.recv()
            if kind == "step":
                steps.append(payload)
                print(
                    f"    {payload['name']:32s} rss {payload['rss_bytes'] / MIB:8.0f} MiB"
                    f"  peak {payload['peak_wset_bytes'] / MIB:8.0f} MiB"
                    f"  t={payload['elapsed_seconds']:.1f}s"
                )
            elif kind == "done":
                status = "ok"
                break
            else:
                status, detail = "error", payload
                break
    except EOFError:
        status, detail = "error", "child exited without reporting"
    finally:
        parent.close()
        process.join(timeout=30)
        if process.is_alive():
            process.kill()
            process.join()
    return {
        "status": status,
        "detail": detail,
        "wall_seconds": round(time.perf_counter() - started, 3),
        "steps": steps,
        "peak_wset_bytes": max((step["peak_wset_bytes"] for step in steps), default=0),
    }


def _checkpoint_composition(checkpoint: Path) -> dict:
    import torch

    state = torch.load(checkpoint, map_location="cpu", weights_only=True, mmap=True)["model"]
    modules: dict[str, dict] = OrderedDict()
    text_breakdown = {
        "embeddings": 0,
        "text_layers": 0,
        "fusion_layers": 0,
        "mlm_head_and_other": 0,
    }
    fusion_layer = None
    for key, tensor in state.items():
        size = tensor.numel() * tensor.element_size()
        module = key.split(".")[0]
        row = modules.setdefault(
            module, {"bytes": 0, "tensors": 0, "used_in_inference": module in INFERENCE_MODULES}
        )
        row["bytes"] += size
        row["tensors"] += 1
        if module == "text_encoder":
            if key.startswith(TEXT_ENCODER_INFERENCE_PREFIXES):
                text_breakdown["embeddings"] += size
            elif key.startswith(TEXT_ENCODER_LAYER_PREFIX):
                layer = int(key[len(TEXT_ENCODER_LAYER_PREFIX) :].split(".")[0])
                if fusion_layer is None:
                    fusion_layer = _fusion_layer()
                if layer < fusion_layer:
                    text_breakdown["text_layers"] += size
                else:
                    text_breakdown["fusion_layers"] += size
            else:
                text_breakdown["mlm_head_and_other"] += size
    total = sum(row["bytes"] for row in modules.values())
    needed = sum(row["bytes"] for row in modules.values() if row["used_in_inference"])
    minimal = needed - text_breakdown["fusion_layers"] - text_breakdown["mlm_head_and_other"]
    return {
        "file_bytes": checkpoint.stat().st_size,
        "state_keys": len(state),
        "state_bytes_total": total,
        "state_bytes_used_in_inference": needed,
        "state_bytes_minimal_text_mode_only": minimal,
        "fusion_layer_index": fusion_layer,
        "by_module": {
            name: row for name, row in sorted(modules.items(), key=lambda item: -item[1]["bytes"])
        },
        "text_encoder_breakdown": text_breakdown,
    }


def _fusion_layer() -> int:
    vendor = Path(__file__).resolve().parents[1] / "src/person_search/ai/encoders/rasa_vendor"
    return int(
        json.loads((vendor / "config_bert.json").read_text(encoding="utf-8"))["fusion_layer"]
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--registry", required=True)
    parser.add_argument("--artifact-root", required=True)
    parser.add_argument("--settings", required=True)
    parser.add_argument(
        "--tag", required=True, help="label of this code state, e.g. before, after-a1"
    )
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--skip-stepwise", action="store_true")
    args = parser.parse_args()

    from person_search.ai.registry import load_registry

    registry = load_registry(
        args.registry, artifact_root=args.artifact_root, preflight_available={"rasa_cuhk_pedes_v1"}
    )
    assert registry.encoder is not None
    checkpoint = (Path(args.artifact_root) / registry.encoder.artifact.relative_path).resolve()
    vendor_dir = Path(__file__).resolve().parents[1] / "src/person_search/ai/encoders/rasa_vendor"

    import torch

    print(f"[{args.tag}] checkpoint composition")
    composition = _checkpoint_composition(checkpoint)
    for name, row in composition["by_module"].items():
        flag = "inference" if row["used_in_inference"] else "training only"
        print(f"    {name:22s} {row['bytes'] / MIB:8.1f} MiB  {flag}")
    print(
        f"    total {composition['state_bytes_total'] / MIB:,.0f} MiB, used in inference"
        f" {composition['state_bytes_used_in_inference'] / MIB:,.0f} MiB, minimal (text mode only)"
        f" {composition['state_bytes_minimal_text_mode_only'] / MIB:,.0f} MiB"
    )

    runs = {}
    if not args.skip_stepwise:
        print(f"[{args.tag}] stepwise load (training-time ALBEF module)")
        vocab = (
            Path(args.artifact_root) / "model_artifacts" / "bert-base-uncased-vocab.txt"
        ).resolve()
        runs["stepwise"] = _run_child(
            _stepwise_child, (str(checkpoint), str(vendor_dir), str(vocab))
        )
    print(f"[{args.tag}] production path (RasaRuntimeFactory.load)")
    runs["production_path"] = _run_child(
        _production_child, (args.registry, args.artifact_root, args.settings)
    )

    report = {
        "schema": "person-search-encoder-memory/v1",
        "tag": args.tag,
        "measured_at": datetime.now(UTC).isoformat(),
        "method": {
            "memory": "psutil RSS of the child itself after gc.collect(); peak_wset is the Windows "
            "peak working set of that process since start",
            "note": "file-backed pages of the mmap'd checkpoint count in RSS while referenced",
        },
        "environment": {
            "platform": platform.platform(),
            "python": sys.version.split()[0],
            "torch": torch.__version__,
            "threads": torch.get_num_threads(),
        },
        "encoder": {
            "id": registry.encoder.id,
            "version": registry.encoder.version,
            "sha256": registry.encoder.artifact.sha256,
        },
        "checkpoint": composition,
        "runs": runs,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"written {args.output}")
    return 0 if all(run["status"] == "ok" for run in runs.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
