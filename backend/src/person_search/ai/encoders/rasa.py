"""Pinned RaSa CUHK-PEDES runtime factory and shared image/text preprocessing."""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path, PurePosixPath
from typing import Any

from PIL import Image, ImageOps

from person_search.ai.registry import EncoderEntry


def _sha256(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


@dataclass(frozen=True, slots=True)
class RasaRuntimeSettings:
    upstream_commit: str
    image_size: int
    image_mean: tuple[float, float, float]
    image_std: tuple[float, float, float]
    resize_interpolation: str
    tokenizer: str
    tokenizer_vocab_path: str
    tokenizer_vocab_sha256: str
    maximum_text_tokens: int
    embedding_dimension: int
    l2_normalized: bool
    itm_rerank_supported: bool
    itm_rerank_top_k: int

    def __post_init__(self) -> None:
        if len(self.upstream_commit) != 40 or any(
            char not in "0123456789abcdef" for char in self.upstream_commit
        ):
            raise ValueError("upstream_commit must be a full lowercase Git SHA.")
        integer_fields = (
            "image_size",
            "maximum_text_tokens",
            "embedding_dimension",
            "itm_rerank_top_k",
        )
        for name in integer_fields:
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int) or value < 1:
                raise ValueError(f"{name} must be a positive integer.")
        for name in ("image_mean", "image_std"):
            values = tuple(getattr(self, name))
            if len(values) != 3 or not all(
                isinstance(value, (int, float)) and math.isfinite(value) for value in values
            ):
                raise ValueError(f"{name} must contain three finite numbers.")
            if name == "image_std" and any(value <= 0 for value in values):
                raise ValueError("image_std values must be positive.")
            object.__setattr__(self, name, values)
        if self.resize_interpolation != "bicubic":
            raise ValueError("RaSa checkpoint requires bicubic resize.")
        if self.tokenizer != "bert-base-uncased":
            raise ValueError("RaSa checkpoint requires bert-base-uncased.")
        if len(self.tokenizer_vocab_sha256) != 64:
            raise ValueError("tokenizer_vocab_sha256 must be a SHA-256 digest.")
        path = PurePosixPath(self.tokenizer_vocab_path)
        if path.is_absolute() or ".." in path.parts:
            raise ValueError("tokenizer_vocab_path must stay inside artifact_root.")
        if self.embedding_dimension != 256 or self.l2_normalized is not True:
            raise ValueError("RaSa CUHK-PEDES vector space is fixed at normalized 256 dimensions.")


def load_rasa_settings(path: str | Path) -> RasaRuntimeSettings:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    expected = {"schema_version", *RasaRuntimeSettings.__dataclass_fields__}
    if not isinstance(payload, dict) or set(payload) != expected:
        raise ValueError("RaSa runtime settings contain missing or unknown fields.")
    if payload.pop("schema_version") != "rasa-runtime/v1":
        raise ValueError("Unsupported RaSa runtime settings schema.")
    return RasaRuntimeSettings(**payload)


@dataclass(frozen=True, slots=True)
class RasaCheckpointMetadata:
    state_keys: int
    image_projection_shape: tuple[int, int]
    text_projection_shape: tuple[int, int]
    position_embedding_shape: tuple[int, int, int]


class RasaPreprocessor:
    def __init__(self, settings: RasaRuntimeSettings, *, vocab_path: Path) -> None:
        self.settings = settings
        self.vocab_path = vocab_path
        self._tokenizer = None

    def image(self, image: Image.Image):
        if not isinstance(image, Image.Image):
            raise TypeError("RaSa image preprocessing requires a PIL image.")
        import torch
        from torchvision.transforms import InterpolationMode
        from torchvision.transforms import functional as vision

        oriented = ImageOps.exif_transpose(image).convert("RGB")
        resized = vision.resize(
            oriented,
            [self.settings.image_size, self.settings.image_size],
            interpolation=InterpolationMode.BICUBIC,
            antialias=True,
        )
        tensor = vision.pil_to_tensor(resized).to(dtype=torch.float32).div_(255)
        return vision.normalize(tensor, self.settings.image_mean, self.settings.image_std)

    def text(self, text: str):
        if not isinstance(text, str) or not text.strip():
            raise ValueError("RaSa text preprocessing requires non-empty text.")
        if self._tokenizer is None:
            # RaSa trains and evaluates with its own copy of the BERT tokenizer, which writes
            # "[CLS] X" without the closing [SEP]; the stock Transformers tokenizer appends [SEP],
            # which the checkpoint never saw and which lowers text retrieval (B1, 5 Oct 2026).
            from person_search.ai.encoders.rasa_vendor.tokenization_bert import BertTokenizer

            self._tokenizer = BertTokenizer(
                vocab_file=str(self.vocab_path),
                do_lower_case=True,
            )
        return self._tokenizer(
            text,
            padding="max_length",
            truncation=True,
            max_length=self.settings.maximum_text_tokens,
            return_tensors="pt",
        )


class RasaRuntime:
    def __init__(
        self,
        model: Any,
        preprocessor: RasaPreprocessor,
        *,
        device: str,
        fusion_layers_loaded: bool = True,
    ) -> None:
        self.model = model
        self.preprocessor = preprocessor
        self.device = device
        self.fusion_layers_loaded = fusion_layers_loaded

    def image_embedding(self, image: Image.Image):
        import torch
        import torch.nn.functional as functional

        with torch.inference_mode():
            tensor = self.preprocessor.image(image).unsqueeze(0).to(self.device)
            features = self.model.visual_encoder(tensor)
            vector = functional.normalize(self.model.vision_proj(features[:, 0, :]), dim=-1)
        return self._validate(vector)

    def text_embedding(self, text: str):
        import torch
        import torch.nn.functional as functional

        with torch.inference_mode():
            tokens = self.preprocessor.text(text).to(self.device)
            output = self.model.text_encoder.bert(
                tokens.input_ids,
                attention_mask=tokens.attention_mask,
                return_dict=True,
                mode="text",
            )
            vector = functional.normalize(
                self.model.text_proj(output.last_hidden_state[:, 0, :]), dim=-1
            )
        return self._validate(vector)

    def image_tokens(self, image: Image.Image):
        """All image token features of the visual encoder (1, 577, 768), for ITM re-ranking."""

        import torch

        with torch.inference_mode():
            tensor = self.preprocessor.image(image).unsqueeze(0).to(self.device)
            return self.model.visual_encoder(tensor)

    def itm_scores(self, text: str, image_tokens, *, batch_size: int = 8):
        """Image-text matching logits of one text against image token features (N, 577, 768).

        Reproduces the ranking stage of the authors' evaluation: the text is encoded once in
        ``text`` mode, then fused with each candidate's image tokens through the cross-attention
        layers, and the matching head's "match" logit is returned per candidate.
        """

        import torch

        if not self.fusion_layers_loaded:
            raise RuntimeError("ITM re-ranking needs the fusion layers (keep_fusion_layers=True).")
        with torch.inference_mode():
            tokens = self.preprocessor.text(text).to(self.device)
            text_output = self.model.text_encoder.bert(
                tokens.input_ids,
                attention_mask=tokens.attention_mask,
                return_dict=True,
                mode="text",
            )
            text_feat = text_output.last_hidden_state
            scores = []
            for start in range(0, image_tokens.shape[0], batch_size):
                chunk = image_tokens[start : start + batch_size].to(
                    device=self.device, dtype=text_feat.dtype
                )
                fused = self.model.text_encoder.bert(
                    encoder_embeds=text_feat.repeat(chunk.shape[0], 1, 1),
                    attention_mask=tokens.attention_mask.repeat(chunk.shape[0], 1),
                    encoder_hidden_states=chunk,
                    encoder_attention_mask=torch.ones(
                        chunk.shape[:-1], dtype=torch.long, device=self.device
                    ),
                    return_dict=True,
                    mode="fusion",
                )
                scores.append(self.model.itm_head(fused.last_hidden_state[:, 0, :])[:, 1])
            return torch.cat(scores)

    def _validate(self, vector):
        import torch

        if tuple(vector.shape) != (1, 256) or not torch.isfinite(vector).all():
            raise ValueError("RaSa produced an invalid embedding vector.")
        if not torch.allclose(vector.norm(dim=-1), torch.ones(1, device=vector.device), atol=1e-5):
            raise ValueError("RaSa produced a vector that is not L2-normalized.")
        return vector


class RasaRuntimeFactory:
    def __init__(
        self,
        entry: EncoderEntry,
        *,
        artifact_root: str | Path,
        settings: RasaRuntimeSettings,
        device: str = "cpu",
        keep_fusion_layers: bool = False,
    ) -> None:
        if not isinstance(entry, EncoderEntry) or entry.adapter_kind != "rasa":
            raise ValueError("Encoder entry is not a RaSa adapter.")
        if entry.id != "rasa_cuhk_pedes_v1" or entry.version != "rasa_cuhk_pedes_v1":
            raise ValueError("RaSa encoder version does not match the active vector space.")
        if not entry.available:
            raise ValueError("RaSa encoder entry is not available for production.")
        if device not in {item.value for item in entry.devices}:
            raise ValueError("Requested RaSa device is not allowlisted.")
        if entry.dimension != settings.embedding_dimension or not entry.normalized:
            raise ValueError("Registry and RaSa vector-space metadata do not match.")
        if entry.preprocessing_version != "rasa_cuhk_pedes_384_clip_v1":
            raise ValueError("Registry uses an unsupported RaSa preprocessing version.")
        root = Path(artifact_root).resolve()
        checkpoint = (root / Path(*PurePosixPath(entry.artifact.relative_path).parts)).resolve()
        vocab = (root / Path(*PurePosixPath(settings.tokenizer_vocab_path).parts)).resolve()
        if not checkpoint.is_relative_to(root) or not checkpoint.is_file():
            raise ValueError("RaSa checkpoint is unavailable.")
        if not vocab.is_relative_to(root) or not vocab.is_file():
            raise ValueError("RaSa tokenizer vocabulary is unavailable.")
        if _sha256(checkpoint) != entry.artifact.sha256:
            raise ValueError("RaSa checkpoint checksum changed.")
        if _sha256(vocab) != settings.tokenizer_vocab_sha256:
            raise ValueError("RaSa tokenizer vocabulary checksum changed.")
        self.entry = entry
        self.settings = settings
        self.device = device
        self.keep_fusion_layers = keep_fusion_layers
        self.checkpoint = checkpoint
        self.vocab = vocab

    def inspect_checkpoint(self) -> RasaCheckpointMetadata:
        import torch

        checkpoint = torch.load(
            self.checkpoint,
            map_location="cpu",
            weights_only=True,
            mmap=True,
        )
        if not isinstance(checkpoint, dict) or not isinstance(checkpoint.get("model"), dict):
            raise ValueError("RaSa checkpoint must contain a model state dictionary.")
        state = checkpoint["model"]
        metadata = RasaCheckpointMetadata(
            len(state),
            tuple(state["vision_proj.weight"].shape),
            tuple(state["text_proj.weight"].shape),
            tuple(state["visual_encoder.pos_embed"].shape),
        )
        expected = RasaCheckpointMetadata(849, (256, 768), (256, 768), (1, 577, 768))
        if metadata != expected:
            raise ValueError("RaSa checkpoint architecture does not match CUHK-PEDES v1.")
        return metadata

    def load(self, *, full_training_module: bool = False) -> RasaRuntime:
        """Load the encoders for inference.

        By default only the modules that ``image_embedding`` and ``text_embedding`` read are
        built, on the ``meta`` device, and the matching checkpoint tensors are assigned to them
        without an intermediate random initialisation, so neither the momentum copies nor the
        contrastive queues of the training checkpoint ever occupy memory. ``full_training_module``
        rebuilds the original ``ALBEF`` class instead; it exists for equivalence checks and costs
        about twice the steady memory and four times the peak (``tools/measure_encoder_memory.py``).
        """

        import torch

        self.inspect_checkpoint()
        preprocessor = RasaPreprocessor(self.settings, vocab_path=self.vocab)
        bert_config = str(Path(__file__).with_name("rasa_vendor") / "config_bert.json")
        checkpoint = torch.load(
            self.checkpoint,
            map_location="cpu",
            weights_only=True,
            mmap=True,
        )
        if full_training_module:
            from person_search.ai.encoders.rasa_vendor.model_person_search import ALBEF

            config = {
                "bert_config": bert_config,
                "embed_dim": self.settings.embedding_dimension,
                "image_res": self.settings.image_size,
                "vision_width": 768,
                "temp": 0.07,
                "mlm_probability": 0.15,
                "mrtd_mask_probability": 0.3,
                "queue_size": 65536,
                "momentum": 0.995,
            }
            model = ALBEF(config=config, text_encoder=None, tokenizer=None)
            result = model.load_state_dict(checkpoint["model"], strict=False)
            if result.missing_keys or result.unexpected_keys:
                raise ValueError(
                    "RaSa checkpoint state does not match the vendored model architecture."
                )
            fusion_layers_loaded = True
        else:
            from person_search.ai.encoders.rasa_vendor.inference_model import RasaInferenceModel

            with torch.device("meta"):
                model = RasaInferenceModel(
                    bert_config_path=bert_config,
                    image_res=self.settings.image_size,
                    embed_dim=self.settings.embedding_dimension,
                    keep_fusion_layers=self.keep_fusion_layers,
                )
            state = RasaInferenceModel.select_state(
                checkpoint["model"],
                fusion_layer=model.fusion_layer,
                keep_fusion_layers=self.keep_fusion_layers,
            )
            try:
                model.load_state_dict(state, strict=True, assign=True)
            except RuntimeError as exc:
                raise ValueError(
                    "RaSa checkpoint state does not match the inference model architecture."
                ) from exc
            left_on_meta = [
                name
                for name, tensor in list(model.named_parameters()) + list(model.named_buffers())
                if tensor.device.type == "meta"
            ]
            if left_on_meta:
                raise ValueError(
                    "RaSa inference model has tensors the checkpoint did not fill: "
                    + ", ".join(left_on_meta[:5])
                )
            fusion_layers_loaded = self.keep_fusion_layers
        del checkpoint
        model.eval().to(self.device)
        return RasaRuntime(
            model, preprocessor, device=self.device, fusion_layers_loaded=fusion_layers_loaded
        )
