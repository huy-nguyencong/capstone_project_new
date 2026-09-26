from __future__ import annotations

import io
import math

import pytest
from PIL import Image

from person_search.demo import DemoEncoder, DemoEncoderGateway
from person_search.services.searches import (
    EncoderUnavailableError,
    InvalidQueryImageError,
    SearchService,
    attributes_prompt,
    decode_query_image,
)

pytestmark = pytest.mark.unit


def _image_bytes(*, format: str = "JPEG") -> bytes:
    stream = io.BytesIO()
    Image.new("RGB", (32, 48), (150, 20, 30)).save(stream, format=format)
    return stream.getvalue()


def test_demo_query_encoder_requires_explicit_opt_in() -> None:
    production = SearchService(lambda: None, object())
    with pytest.raises(EncoderUnavailableError, match="not enabled"):
        production.gateway("fake_demo_v1")

    demo = SearchService(lambda: None, object(), allow_demo=True)
    assert isinstance(demo.gateway("fake_demo_v1"), DemoEncoderGateway)


def test_demo_query_image_uses_the_same_vector_space_as_worker() -> None:
    content = _image_bytes()
    image = decode_query_image(content)

    query_vector = DemoEncoderGateway().image(content, version="fake_demo_v1", dimension=256)
    worker_vector = DemoEncoder().encode(image)

    assert query_vector == worker_vector
    assert math.isclose(sum(value * value for value in query_vector), 1.0)


@pytest.mark.parametrize("content", [b"", b"not-an-image"])
def test_invalid_query_image_is_rejected(content: bytes) -> None:
    with pytest.raises(InvalidQueryImageError):
        decode_query_image(content)


def test_attribute_prompt_is_deterministic_english() -> None:
    assert (
        attributes_prompt(
            {
                "upper_color": "red",
                "lower_color": "black",
                "upper_type": "jacket",
                "has_backpack": True,
            }
        )
        == "A person wearing red jacket and black pants, carrying a backpack."
    )


def test_attribute_prompt_requires_supported_non_empty_attributes() -> None:
    with pytest.raises(ValueError):
        attributes_prompt({})
    with pytest.raises(ValueError):
        attributes_prompt({"hat": "red"})
    with pytest.raises(ValueError):
        attributes_prompt({"upper_color": "purple"})
    with pytest.raises(ValueError):
        attributes_prompt({"upper_type": "dress", "lower_color": "black"})
