"""Bounded representative-frame selection for completed tracks."""

from person_search.ai.selectors.representative import (
    RepresentativeFrameSelector,
    SelectorMetrics,
    SelectorSettings,
    crop_representative,
    load_selector_settings,
)

__all__ = [
    "RepresentativeFrameSelector",
    "SelectorMetrics",
    "SelectorSettings",
    "crop_representative",
    "load_selector_settings",
]
