from __future__ import annotations

import io
import math

import pytest
from PIL import Image

from person_search.ai.encoders.image import (
    ImageEncoderSettings,
    RasaImageEncoder,
    RasaImageQueryGateway,
)
from person_search.workers.contracts import ModelLineage
from person_search.workers.errors import AIErrorCode, AIWorkerError

pytestmark = pytest.mark.unit

LINEAGE = ModelLineage("rasa_cuhk_pedes_v1", "rasa_cuhk_pedes_v1", "a" * 64)


class Backend:
    def __init__(self, output=None, error=None):
        self.output = output or [1.0] + [0.0] * 255
        self.error = error
        self.opened = False
        self.closed = False
        self.seen = []

    def open(self):
        self.opened = True

    def encode(self, image, *, timeout_seconds):
        self.seen.append((image.mode, image.size, timeout_seconds))
        if self.error:
            raise self.error
        return self.output

    def close(self):
        self.closed = True


def opened(backend=None, **settings):
    backend = backend or Backend()
    encoder = RasaImageEncoder(
        backend,
        lineage=LINEAGE,
        dimension=256,
        settings=ImageEncoderSettings(**settings),
    )
    encoder.open()
    return encoder, backend


@pytest.mark.parametrize("mode", ["RGB", "L", "RGBA"])
def test_valid_channels_share_the_same_vector_contract(mode):
    encoder, backend = opened()
    vector = encoder.encode(Image.new(mode, (32, 48)))
    assert vector.dimension == 256
    assert vector.encoder == LINEAGE
    assert math.isclose(sum(value * value for value in vector.values), 1.0)
    assert backend.seen[0][:2] == (mode, (32, 48))


def test_rejects_oversized_image_before_backend():
    encoder, backend = opened(max_pixels=100)
    with pytest.raises(ValueError, match="exceed"):
        encoder.encode(Image.new("RGB", (11, 10)))
    assert backend.seen == []


@pytest.mark.parametrize(
    "output", [[float("nan")] + [0.0] * 255, [1.0] * 255, [2.0] + [0.0] * 255]
)
def test_rejects_invalid_backend_vector(output):
    encoder, backend = opened(Backend(output=output))
    with pytest.raises(AIWorkerError) as caught:
        encoder.encode(Image.new("RGB", (8, 8)))
    assert caught.value.code is AIErrorCode.IMAGE_ENCODER_OUTPUT_INVALID
    assert backend.closed


def test_timeout_is_sanitized_and_closes_backend():
    encoder, backend = opened(Backend(error=TimeoutError("private detail")))
    with pytest.raises(AIWorkerError) as caught:
        encoder.encode(Image.new("RGB", (8, 8)))
    assert caught.value.code is AIErrorCode.IMAGE_ENCODER_INFERENCE_FAILED
    assert "private detail" not in str(caught.value)
    assert backend.closed


def test_query_gateway_decodes_grayscale_and_is_deterministic():
    encoder, backend = opened()
    gateway = RasaImageQueryGateway(encoder)
    stream = io.BytesIO()
    Image.new("L", (20, 30), 127).save(stream, format="PNG")
    first = gateway.image(stream.getvalue(), version=LINEAGE.version, dimension=256)
    second = gateway.image(stream.getvalue(), version=LINEAGE.version, dimension=256)
    assert first == second
    assert backend.seen == [("RGB", (20, 30), 120.0)] * 2


def test_query_gateway_rejects_corrupt_image_and_wrong_lineage():
    encoder, _ = opened()
    gateway = RasaImageQueryGateway(encoder)
    with pytest.raises(ValueError, match="metadata"):
        gateway.image(b"not-an-image", version="wrong", dimension=256)
    with pytest.raises(ValueError, match="invalid"):
        gateway.image(b"not-an-image", version=LINEAGE.version, dimension=256)
