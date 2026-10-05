from __future__ import annotations

import hashlib
import json
from dataclasses import replace
from pathlib import Path

import pytest
from PIL import Image

from person_search.ai.encoders import (
    RasaRuntimeFactory,
    RasaRuntimeSettings,
    load_rasa_settings,
)
from person_search.ai.registry import (
    ArtifactReference,
    DeviceKind,
    EncoderEntry,
    Provenance,
)

pytestmark = pytest.mark.unit

CONFIG = Path(__file__).parents[2] / "config"


def settings() -> RasaRuntimeSettings:
    return load_rasa_settings(CONFIG / "rasa_cuhk_pedes_runtime.json")


def entry(path: str, digest: str, *, preprocessing="rasa_cuhk_pedes_384_clip_v1"):
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
        preprocessing,
    )


def test_runtime_settings_lock_upstream_vector_space() -> None:
    value = settings()
    assert value.upstream_commit == "bd16aa1a15f149548a90d196fcf10a27d7ab7c66"
    assert value.image_size == 384
    assert value.image_mean == (0.48145466, 0.4578275, 0.40821073)
    assert value.image_std == (0.26862954, 0.26130258, 0.27577711)
    assert value.maximum_text_tokens == 50
    assert value.embedding_dimension == 256 and value.l2_normalized
    assert value.itm_rerank_supported and value.itm_rerank_top_k == 128


@pytest.mark.model_real(modules=("torch", "torchvision"))
def test_image_preprocessing_is_deterministic_rgb_bicubic_snapshot() -> None:
    value = settings()
    from person_search.ai.encoders.rasa import RasaPreprocessor

    processor = RasaPreprocessor(
        value,
        vocab_path=CONFIG / value.tokenizer_vocab_path,
    )
    image = Image.new("RGB", (7, 11), (255, 0, 127))
    first = processor.image(image)
    second = processor.image(image)

    assert tuple(first.shape) == (3, 384, 384)
    assert first.equal(second)
    assert first[:, 100, 100].tolist() == pytest.approx(
        [
            (1 - value.image_mean[0]) / value.image_std[0],
            (0 - value.image_mean[1]) / value.image_std[1],
            ((127 / 255) - value.image_mean[2]) / value.image_std[2],
        ],
        abs=1e-6,
    )


@pytest.mark.model_real(modules=("transformers",))
def test_tokenizer_is_offline_uncased_padded_and_truncated() -> None:
    from person_search.ai.encoders.rasa import RasaPreprocessor

    value = settings()
    processor = RasaPreprocessor(value, vocab_path=CONFIG / value.tokenizer_vocab_path)
    tokens = processor.text("A PERSON wearing a BLUE jacket " * 20)

    assert tuple(tokens.input_ids.shape) == (1, 50)
    assert tokens.input_ids[0, 0].item() == 101
    # RaSa's tokenizer writes "[CLS] X" with no closing [SEP], as the checkpoint was trained.
    assert 102 not in tokens.input_ids[0].tolist()
    assert tokens.input_ids[0, -1].item() != 0
    short = processor.text("A person wearing a blue jacket.")
    assert short.input_ids[0, :2].tolist() == [101, 1037]
    assert 102 not in short.input_ids[0].tolist()
    assert int(short.attention_mask.sum()) == 8
    lower = processor.text("Person").input_ids[0, 1].item()
    upper = processor.text("PERSON").input_ids[0, 1].item()
    assert lower == upper


def test_settings_loader_rejects_unknown_fields(tmp_path: Path) -> None:
    source = CONFIG / "rasa_cuhk_pedes_runtime.json"
    payload = json.loads(source.read_text(encoding="utf-8"))
    payload["unknown"] = True
    target = tmp_path / "runtime.json"
    target.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValueError, match="missing or unknown"):
        load_rasa_settings(target)


def test_factory_rejects_checkpoint_and_vocab_checksum_changes(tmp_path: Path) -> None:
    checkpoint = tmp_path / "model.pth"
    checkpoint.write_bytes(b"checkpoint")
    vocab = tmp_path / "vocab.txt"
    vocab.write_bytes(b"vocab")
    checkpoint_hash = hashlib.sha256(checkpoint.read_bytes()).hexdigest()
    vocab_hash = hashlib.sha256(vocab.read_bytes()).hexdigest()
    value = replace(
        settings(),
        tokenizer_vocab_path="vocab.txt",
        tokenizer_vocab_sha256=vocab_hash,
    )
    model_entry = entry("model.pth", checkpoint_hash)
    RasaRuntimeFactory(model_entry, artifact_root=tmp_path, settings=value)

    checkpoint.write_bytes(b"changed")
    with pytest.raises(ValueError, match="checkpoint checksum changed"):
        RasaRuntimeFactory(model_entry, artifact_root=tmp_path, settings=value)
    checkpoint.write_bytes(b"checkpoint")
    vocab.write_bytes(b"changed")
    with pytest.raises(ValueError, match="vocabulary checksum changed"):
        RasaRuntimeFactory(model_entry, artifact_root=tmp_path, settings=value)


def test_factory_rejects_vector_or_preprocessing_version_mismatch(tmp_path: Path) -> None:
    checkpoint = tmp_path / "model.pth"
    checkpoint.write_bytes(b"checkpoint")
    vocab = tmp_path / "vocab.txt"
    vocab.write_bytes(b"vocab")
    value = replace(
        settings(),
        tokenizer_vocab_path="vocab.txt",
        tokenizer_vocab_sha256=hashlib.sha256(vocab.read_bytes()).hexdigest(),
    )
    model_entry = entry("model.pth", hashlib.sha256(checkpoint.read_bytes()).hexdigest())

    with pytest.raises(ValueError, match="vector-space"):
        RasaRuntimeFactory(
            replace(model_entry, dimension=512),
            artifact_root=tmp_path,
            settings=value,
        )
    with pytest.raises(ValueError, match="preprocessing"):
        RasaRuntimeFactory(
            replace(model_entry, preprocessing_version="wrong"),
            artifact_root=tmp_path,
            settings=value,
        )
    with pytest.raises(ValueError, match="version"):
        RasaRuntimeFactory(
            replace(model_entry, version="another_space"),
            artifact_root=tmp_path,
            settings=value,
        )


@pytest.mark.model_real(modules=("torch",), artifacts=("rasa_checkpoint",))
def test_official_checkpoint_architecture_metadata() -> None:
    digest = "bc85da09c2991d5de503c2c2ac4f032e20cc536fec5094f0acff45e93d0104d2"
    factory = RasaRuntimeFactory(
        entry("model_artifacts/rasa_cuhk_pedes_v1.pth", digest),
        artifact_root=CONFIG,
        settings=settings(),
    )

    metadata = factory.inspect_checkpoint()

    assert metadata.state_keys == 849
    assert metadata.image_projection_shape == (256, 768)
    assert metadata.text_projection_shape == (256, 768)
    assert metadata.position_embedding_shape == (1, 577, 768)
