"""Inference-only RaSa module: the two encoders and two projections, nothing else.

The published checkpoint was saved from the training-time ``ALBEF`` class, which also holds a
momentum copy of both encoders, three contrastive queues and three auxiliary heads. Image and text
embeddings only read ``visual_encoder``, ``vision_proj``, the ``text`` layers of
``text_encoder.bert`` and ``text_proj``. This module builds exactly those parts, keeps the same
parameter names so the checkpoint loads unchanged, and leaves the rest of the file untouched.
"""

from __future__ import annotations

from functools import partial

from torch import nn

from person_search.ai.encoders.rasa_vendor.vit import VisionTransformer
from person_search.ai.encoders.rasa_vendor.xbert import BertConfig, BertModel

VISUAL_PREFIX = "visual_encoder."
TEXT_BERT_PREFIX = "text_encoder.bert."
TEXT_LAYER_PREFIX = "text_encoder.bert.encoder.layer."
PROJECTION_PREFIXES = ("vision_proj.", "text_proj.")
ITM_PREFIX = "itm_head."


class _TextEncoderShell(nn.Module):
    """Keeps the ``text_encoder.bert`` prefix of ``BertForMaskedLM``, without its MLM head."""

    def __init__(self, config: BertConfig) -> None:
        super().__init__()
        self.bert = BertModel(config, add_pooling_layer=False)


class RasaInferenceModel(nn.Module):
    def __init__(
        self,
        *,
        bert_config_path: str,
        image_res: int,
        embed_dim: int,
        vision_width: int = 768,
        keep_fusion_layers: bool = False,
    ) -> None:
        super().__init__()
        self.visual_encoder = VisionTransformer(
            img_size=image_res,
            patch_size=16,
            embed_dim=768,
            depth=12,
            num_heads=12,
            mlp_ratio=4,
            qkv_bias=True,
            norm_layer=partial(nn.LayerNorm, eps=1e-6),
        )
        bert_config = BertConfig.from_json_file(bert_config_path)
        self.fusion_layer = int(bert_config.fusion_layer)
        self.keep_fusion_layers = keep_fusion_layers
        if not keep_fusion_layers:
            # ``mode="text"`` runs layers [0, fusion_layer); the fusion layers and the MLM head
            # only serve ITM re-ranking, which the application keeps disabled.
            bert_config.num_hidden_layers = self.fusion_layer
        self.text_encoder = _TextEncoderShell(bert_config)
        self.vision_proj = nn.Linear(vision_width, embed_dim)
        self.text_proj = nn.Linear(bert_config.hidden_size, embed_dim)
        if keep_fusion_layers:
            # The image-text matching head scores a (text, image) pair from the fused [CLS].
            self.itm_head = nn.Linear(bert_config.hidden_size, 2)

    @staticmethod
    def select_state(state: dict, *, fusion_layer: int, keep_fusion_layers: bool) -> dict:
        """Keep the checkpoint entries this module owns, in checkpoint order."""

        selected = {}
        for key, value in state.items():
            if key.startswith(VISUAL_PREFIX) or key.startswith(PROJECTION_PREFIXES):
                selected[key] = value
            elif key.startswith(ITM_PREFIX):
                if keep_fusion_layers:
                    selected[key] = value
            elif key.startswith(TEXT_BERT_PREFIX):
                if not keep_fusion_layers and key.startswith(TEXT_LAYER_PREFIX):
                    layer = int(key[len(TEXT_LAYER_PREFIX) :].split(".", 1)[0])
                    if layer >= fusion_layer:
                        continue
                selected[key] = value
        return selected
