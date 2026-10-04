"""The inference-only RaSa module keeps exactly the checkpoint entries that embeddings read."""

from __future__ import annotations

from pathlib import Path

import pytest

from person_search.ai.encoders import RasaRuntimeFactory, RasaRuntimeSettings, load_rasa_settings
from person_search.ai.encoders.rasa_vendor.inference_model import RasaInferenceModel
from person_search.ai.registry import ArtifactReference, DeviceKind, EncoderEntry, Provenance

pytestmark = pytest.mark.unit

CONFIG = Path(__file__).parents[2] / "config"
FUSION_LAYER = 6


def settings() -> RasaRuntimeSettings:
    return load_rasa_settings(CONFIG / "rasa_cuhk_pedes_runtime.json")


def entry(path: str, digest: str) -> EncoderEntry:
    return EncoderEntry(
        "rasa_cuhk_pedes_v1",
        "RaSa",
        "rasa_cuhk_pedes_v1",
        "test",
        "rasa",
        ArtifactReference(path, digest),
        (DeviceKind.CPU,),
        (3, 384, 384),
        Provenance(
            "rasa-person-retrieval",
            "bd16aa1a15f149548a90d196fcf10a27d7ab7c66",
            "https://github.com/Flame-Chasers/RaSa",
            None,
            "MIT",
            True,
            "approved",
        ),
        True,
        (),
        256,
        True,
        "rasa_cuhk_pedes_384_clip_v1",
    )


def _checkpoint_like_state() -> dict[str, int]:
    """Key layout of the published checkpoint, with one entry per module kind."""

    state = {
        "temp": 0,
        "image_queue": 0,
        "text_queue": 0,
        "idx_queue": 0,
        "queue_ptr": 0,
        "visual_encoder.cls_token": 0,
        "visual_encoder.blocks.0.attn.qkv.weight": 0,
        "visual_encoder_m.cls_token": 0,
        "vision_proj.weight": 0,
        "vision_proj_m.weight": 0,
        "text_proj.bias": 0,
        "text_proj_m.bias": 0,
        "itm_head.weight": 0,
        "prd_head.weight": 0,
        "mrtd_head.weight": 0,
        "text_encoder.bert.embeddings.position_ids": 0,
        "text_encoder.bert.embeddings.word_embeddings.weight": 0,
        "text_encoder.cls.predictions.decoder.weight": 0,
        "text_encoder_m.bert.embeddings.word_embeddings.weight": 0,
    }
    for layer in range(12):
        state[f"text_encoder.bert.encoder.layer.{layer}.attention.self.query.weight"] = 0
        state[f"text_encoder_m.bert.encoder.layer.{layer}.attention.self.query.weight"] = 0
    for layer in range(FUSION_LAYER, 12):
        state[f"text_encoder.bert.encoder.layer.{layer}.crossattention.self.query.weight"] = 0
    return state


def test_select_state_keeps_only_the_inference_modules_without_fusion_layers() -> None:
    selected = RasaInferenceModel.select_state(
        _checkpoint_like_state(), fusion_layer=FUSION_LAYER, keep_fusion_layers=False
    )

    assert set(selected) == {
        "visual_encoder.cls_token",
        "visual_encoder.blocks.0.attn.qkv.weight",
        "vision_proj.weight",
        "text_proj.bias",
        "text_encoder.bert.embeddings.position_ids",
        "text_encoder.bert.embeddings.word_embeddings.weight",
        *(
            f"text_encoder.bert.encoder.layer.{layer}.attention.self.query.weight"
            for layer in range(FUSION_LAYER)
        ),
    }
    assert not any("_m." in key or key.endswith("_queue") for key in selected)
    assert not any(key.startswith("text_encoder.cls.") for key in selected)
    assert not any("crossattention" in key for key in selected)


def test_select_state_keeps_fusion_layers_on_request_but_never_training_parts() -> None:
    selected = RasaInferenceModel.select_state(
        _checkpoint_like_state(), fusion_layer=FUSION_LAYER, keep_fusion_layers=True
    )

    layers = {
        int(key.split(".")[4])
        for key in selected
        if key.startswith("text_encoder.bert.encoder.layer.")
    }
    assert layers == set(range(12))
    assert any("crossattention" in key for key in selected)
    assert not any("_m." in key or key.endswith("_queue") for key in selected)
    assert "text_encoder.cls.predictions.decoder.weight" not in selected
    assert "itm_head.weight" not in selected


def test_select_state_preserves_checkpoint_order() -> None:
    state = _checkpoint_like_state()
    selected = RasaInferenceModel.select_state(
        state, fusion_layer=FUSION_LAYER, keep_fusion_layers=True
    )
    order = [key for key in state if key in selected]
    assert list(selected) == order


def test_factory_records_fusion_layer_choice(tmp_path: Path) -> None:
    import hashlib

    checkpoint = tmp_path / "model_artifacts" / "rasa.pth"
    checkpoint.parent.mkdir()
    checkpoint.write_bytes(b"weights")
    vocab = tmp_path / "model_artifacts" / "bert-base-uncased-vocab.txt"
    vocab.write_bytes((CONFIG / "model_artifacts" / "bert-base-uncased-vocab.txt").read_bytes())
    digest = hashlib.sha256(b"weights").hexdigest()

    default = RasaRuntimeFactory(
        entry("model_artifacts/rasa.pth", digest), artifact_root=tmp_path, settings=settings()
    )
    with_fusion = RasaRuntimeFactory(
        entry("model_artifacts/rasa.pth", digest),
        artifact_root=tmp_path,
        settings=settings(),
        keep_fusion_layers=True,
    )

    assert default.keep_fusion_layers is False
    assert with_fusion.keep_fusion_layers is True


@pytest.mark.model_real(modules=("torch",), artifacts=("rasa_checkpoint",))
def test_official_checkpoint_loads_inference_module_only() -> None:
    import torch
    from PIL import Image

    digest = "bc85da09c2991d5de503c2c2ac4f032e20cc536fec5094f0acff45e93d0104d2"
    factory = RasaRuntimeFactory(
        entry("model_artifacts/rasa_cuhk_pedes_v1.pth", digest),
        artifact_root=CONFIG,
        settings=settings(),
    )

    runtime = factory.load()

    names = {name for name, _ in runtime.model.named_parameters()}
    assert runtime.fusion_layers_loaded is False
    assert not any("_m." in name or "itm_head" in name or ".cls." in name for name in names)
    assert not any("encoder.layer.6." in name for name in names)
    assert all(
        tensor.device.type == "cpu"
        for _, tensor in list(runtime.model.named_parameters())
        + list(runtime.model.named_buffers())
    )
    parameter_bytes = sum(p.numel() * p.element_size() for p in runtime.model.parameters())
    assert parameter_bytes < 650 * 2**20
    image = runtime.image_embedding(Image.new("RGB", (193, 489), (120, 110, 100)))
    text = runtime.text_embedding("a person wearing dark trousers and a light colored top")
    assert tuple(image.shape) == (1, 256) and tuple(text.shape) == (1, 256)
    assert torch.allclose(image.norm(), torch.ones(()), atol=1e-5)
    assert torch.allclose(text.norm(), torch.ones(()), atol=1e-5)
