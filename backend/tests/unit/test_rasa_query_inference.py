from __future__ import annotations

import io
import math

import pytest
from PIL import Image

from person_search.ai.encoders.image import ImageEncoderSettings, RasaImageEncoder
from person_search.ai.encoders.query import (
    MAX_QUERY_TEXT_CHARACTERS,
    RasaQueryInferenceGateway,
    validate_english_description,
)
from person_search.services.searches import attributes_prompt
from person_search.workers.contracts import ModelLineage
from person_search.workers.errors import AIErrorCode, AIWorkerError

pytestmark = pytest.mark.unit

LINEAGE = ModelLineage("rasa_cuhk_pedes_v1", "rasa_cuhk_pedes_v1", "b" * 64)


class MultimodalBackend:
    def __init__(self, *, text_output=None, text_error=None):
        self.vector = [1.0] + [0.0] * 255
        self.text_output = text_output or self.vector
        self.text_error = text_error
        self.image_calls = []
        self.text_calls = []
        self.opened = False
        self.closed = False

    def open(self):
        self.opened = True

    def encode(self, image, *, timeout_seconds):
        self.image_calls.append((image.mode, image.size, timeout_seconds))
        return self.vector

    def encode_text(self, text, *, timeout_seconds):
        self.text_calls.append((text, timeout_seconds))
        if self.text_error:
            raise self.text_error
        return self.text_output

    def close(self):
        self.closed = True


def gateway(backend=None):
    backend = backend or MultimodalBackend()
    encoder = RasaImageEncoder(
        backend,
        lineage=LINEAGE,
        dimension=256,
        settings=ImageEncoderSettings(inference_timeout_seconds=7),
    )
    result = RasaQueryInferenceGateway(encoder, backend)
    result.open()
    return result, backend


def image_bytes():
    stream = io.BytesIO()
    Image.new("RGB", (24, 48), "navy").save(stream, format="PNG")
    return stream.getvalue()


def test_image_and_text_share_vector_space_and_checkpoint_lineage():
    query, backend = gateway()
    image_vector = query.image(image_bytes(), version=LINEAGE.version, dimension=256)
    text_vector = query.text(
        "a person wearing a navy jacket", version=LINEAGE.version, dimension=256
    )
    assert image_vector == text_vector
    assert math.isclose(sum(value * value for value in text_vector), 1.0)
    assert backend.image_calls == [("RGB", (24, 48), 7)]
    assert backend.text_calls == [("a person wearing a navy jacket", 7)]


@pytest.mark.parametrize(
    "text",
    [
        "",
        "   ",
        "áo đỏ và quần đen",
        "person 🚶 in red",
        "a" * (MAX_QUERY_TEXT_CHARACTERS + 1),
    ],
)
def test_text_rejects_empty_long_or_non_english_contract(text):
    query, backend = gateway()
    with pytest.raises(ValueError):
        query.text(text, version=LINEAGE.version, dimension=256)
    assert backend.text_calls == []


def test_text_normalization_is_deterministic_without_translation():
    assert validate_english_description("  A person\n wearing   red. ") == (
        "A person wearing red."
    )


@pytest.mark.parametrize(
    ("attributes", "expected"),
    [
        ({"upper_color": "red"}, "A person wearing a red top."),
        ({"lower_color": "black"}, "A person wearing black pants."),
        ({"upper_type": "dress"}, "A person wearing a dress."),
        ({"lower_type": "skirt", "lower_color": "black"}, "A person wearing a black skirt."),
        ({"gender": "woman", "carrying": "handbag"}, "A woman carrying a handbag."),
        ({"carrying": "shoulder_bag"}, "A person carrying a shoulder bag."),
        (
            {"gender": "man", "upper_color": "orange", "carrying": "suitcase"},
            "A man wearing an orange top, pulling a suitcase.",
        ),
        (
            {"upper_color": "pink", "lower_color": "khaki"},
            "A person wearing a pink top and khaki pants.",
        ),
        ({"gender": "man"}, "A man."),
    ],
)
def test_attribute_prompt_snapshots_are_english_and_deterministic(attributes, expected):
    assert attributes_prompt(attributes) == expected


def test_attribute_prompt_rejects_conflicting_dress_and_pants():
    with pytest.raises(ValueError, match="cannot be combined"):
        attributes_prompt({"upper_type": "dress", "lower_color": "black"})
    with pytest.raises(ValueError, match="cannot be combined"):
        attributes_prompt({"upper_type": "dress", "lower_type": "jeans"})


@pytest.mark.parametrize(
    ("version", "dimension"), [("other", 256), (LINEAGE.version, 128)]
)
def test_gateway_rejects_vector_space_mismatch(version, dimension):
    query, backend = gateway()
    with pytest.raises(ValueError, match="vector space"):
        query.text("a person in red", version=version, dimension=dimension)
    assert backend.text_calls == []


def test_text_timeout_is_sanitized_and_closes_shared_process():
    query, backend = gateway(MultimodalBackend(text_error=TimeoutError("secret")))
    with pytest.raises(AIWorkerError) as caught:
        query.text("a person in red", version=LINEAGE.version, dimension=256)
    assert caught.value.code is AIErrorCode.TEXT_ENCODER_INFERENCE_FAILED
    assert "secret" not in str(caught.value)
    assert backend.closed


@pytest.mark.parametrize("output", [[float("inf")] + [0.0] * 255, [1.0] * 255, [2.0] + [0.0] * 255])
def test_text_rejects_invalid_vectors(output):
    query, backend = gateway(MultimodalBackend(text_output=output))
    with pytest.raises(AIWorkerError) as caught:
        query.text("a person in red", version=LINEAGE.version, dimension=256)
    assert caught.value.code is AIErrorCode.TEXT_ENCODER_OUTPUT_INVALID
    assert backend.closed
