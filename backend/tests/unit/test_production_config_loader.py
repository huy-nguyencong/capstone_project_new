from __future__ import annotations

from types import SimpleNamespace

import pytest

from person_search.ai.config_loader import ProductionModelCandidateLoader


class Component:
    def __init__(self, name, events, *, fail_open=False, fail_close=False):
        self.name = name
        self.events = events
        self.fail_open = fail_open
        self.fail_close = fail_close

    def open(self):
        self.events.append(f"open:{self.name}")
        if self.fail_open:
            raise RuntimeError(f"open {self.name}")

    def close(self):
        self.events.append(f"close:{self.name}")
        if self.fail_close:
            raise RuntimeError(f"close {self.name}")


def loader(events, *, fail_open=None, fail_close=None):
    def builder(name):
        return lambda selection: Component(
            name,
            events,
            fail_open=name == fail_open,
            fail_close=name == fail_close,
        )

    return ProductionModelCandidateLoader(
        (builder("detector"), builder("tracker"), builder("encoder"))
    )


@pytest.mark.unit
def test_candidate_loader_opens_all_models_and_closes_in_reverse_order():
    events = []
    loader(events)(SimpleNamespace(), SimpleNamespace())
    assert events == [
        "open:detector",
        "open:tracker",
        "open:encoder",
        "close:encoder",
        "close:tracker",
        "close:detector",
    ]


@pytest.mark.unit
@pytest.mark.parametrize(
    ("failed", "expected"),
    [
        ("detector", ["open:detector", "close:detector"]),
        (
            "tracker",
            ["open:detector", "open:tracker", "close:tracker", "close:detector"],
        ),
        (
            "encoder",
            [
                "open:detector",
                "open:tracker",
                "open:encoder",
                "close:encoder",
                "close:tracker",
                "close:detector",
            ],
        ),
    ],
)
def test_candidate_loader_cleans_every_constructed_component_after_load_failure(
    failed, expected
):
    events = []
    with pytest.raises(RuntimeError, match=f"open {failed}"):
        loader(events, fail_open=failed)(SimpleNamespace(), SimpleNamespace())
    assert events == expected


@pytest.mark.unit
def test_load_error_wins_but_other_components_close_when_cleanup_also_fails():
    events = []
    subject = loader(events, fail_open="encoder", fail_close="tracker")
    with pytest.raises(RuntimeError, match="open encoder"):
        subject(SimpleNamespace(), SimpleNamespace())
    assert events[-3:] == ["close:encoder", "close:tracker", "close:detector"]
