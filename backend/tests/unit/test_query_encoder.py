from __future__ import annotations

import threading
from types import SimpleNamespace

import pytest

from person_search.services.query_encoder import InProcessQueryEncoder
from person_search.services.searches import EncoderUnavailableError
from person_search.workers.errors import AIErrorCode, AIWorkerError

pytestmark = pytest.mark.unit

ENTRY = SimpleNamespace(version="rasa_v1", dimension=4, available=True)
UNIT = [1.0, 0.0, 0.0, 0.0]


class Gateway:
    def __init__(self, *, open_error=None, text_error=None):
        self.open_error = open_error
        self.text_error = text_error
        self.opened = 0
        self.closed = 0
        self.calls = []

    def open(self):
        self.opened += 1
        if self.open_error is not None:
            raise self.open_error

    def image(self, content, *, version, dimension):
        self.calls.append(("image", version, dimension))
        return tuple(UNIT)

    def text(self, text, *, version, dimension):
        self.calls.append(("text", text))
        if self.text_error is not None:
            raise self.text_error
        return tuple(UNIT)

    def close(self):
        self.closed += 1


def encoder(*gateways, entry=ENTRY):
    pending = list(gateways)
    built = []

    def factory(selection):
        assert selection.encoder is entry
        gateway = pending.pop(0) if pending else Gateway()
        built.append(gateway)
        return gateway

    return InProcessQueryEncoder(SimpleNamespace(encoder=entry), factory), built


def test_loads_once_and_reuses_one_gateway_for_image_and_text():
    subject, built = encoder()

    assert subject.image(b"png", version="rasa_v1", dimension=4) == UNIT
    assert subject.text("A person walking.", version="rasa_v1", dimension=4) == UNIT

    assert len(built) == 1 and built[0].opened == 1
    subject.close()
    assert built[0].closed == 1


def test_version_or_dimension_mismatch_is_unavailable_without_loading():
    subject, built = encoder()
    with pytest.raises(EncoderUnavailableError):
        subject.text("A person.", version="other", dimension=4)
    with pytest.raises(EncoderUnavailableError):
        subject.text("A person.", version="rasa_v1", dimension=8)
    assert built == []


def test_missing_or_unavailable_registry_encoder_is_unavailable():
    for entry in (None, SimpleNamespace(version="rasa_v1", dimension=4, available=False)):
        subject = InProcessQueryEncoder(SimpleNamespace(encoder=entry), lambda _: Gateway())
        with pytest.raises(EncoderUnavailableError):
            subject.image(b"png", version="rasa_v1", dimension=4)


def test_load_failure_is_unavailable_and_retried_on_next_request():
    broken = Gateway(open_error=AIWorkerError(AIErrorCode.IMAGE_ENCODER_UNAVAILABLE))
    subject, built = encoder(broken)

    with pytest.raises(EncoderUnavailableError):
        subject.text("A person.", version="rasa_v1", dimension=4)
    assert broken.closed == 1
    assert subject.text("A person.", version="rasa_v1", dimension=4) == UNIT
    assert len(built) == 2


def test_inference_failure_discards_gateway_and_rebuilds():
    failing = Gateway(text_error=AIWorkerError(AIErrorCode.TEXT_ENCODER_INFERENCE_FAILED))
    subject, built = encoder(failing)

    with pytest.raises(EncoderUnavailableError):
        subject.text("A person.", version="rasa_v1", dimension=4)
    assert failing.closed == 1
    assert subject.text("A person.", version="rasa_v1", dimension=4) == UNIT
    assert len(built) == 2


def test_invalid_query_input_stays_a_validation_error_and_keeps_gateway():
    invalid = Gateway(text_error=ValueError("Text query must be an English description."))
    subject, built = encoder(invalid)

    with pytest.raises(ValueError) as caught:
        subject.text("Người mặc áo đỏ", version="rasa_v1", dimension=4)
    assert not isinstance(caught.value, EncoderUnavailableError)
    assert invalid.closed == 0
    invalid.text_error = None
    subject.text("A person.", version="rasa_v1", dimension=4)
    assert len(built) == 1


def test_concurrent_requests_are_serialized_through_one_model_process():
    active = {"now": 0, "peak": 0}
    lock = threading.Lock()

    class Slow(Gateway):
        def text(self, text, *, version, dimension):
            with lock:
                active["now"] += 1
                active["peak"] = max(active["peak"], active["now"])
            threading.Event().wait(0.01)
            with lock:
                active["now"] -= 1
            return tuple(UNIT)

    subject, built = encoder(Slow())
    threads = [
        threading.Thread(
            target=subject.text, args=("A person.",), kwargs={"version": "rasa_v1", "dimension": 4}
        )
        for _ in range(6)
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert active["peak"] == 1
    assert len(built) == 1
