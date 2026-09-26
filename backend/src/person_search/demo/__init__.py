"""Explicitly opt-in synthetic adapters for local demos and offline tests."""

from person_search.demo.adapters import (
    DEMO_ENCODER_SHA256,
    DEMO_ENCODER_VERSION,
    DEMO_FIXTURE_ID,
    DemoDetector,
    DemoEncoder,
    DemoEncoderGateway,
    DemoPipeline,
    DemoTracker,
    DemoTrackIngestionRequest,
    SyntheticMetadata,
    build_demo_pipeline,
)

__all__ = [
    "DEMO_ENCODER_SHA256",
    "DEMO_ENCODER_VERSION",
    "DEMO_FIXTURE_ID",
    "DemoDetector",
    "DemoEncoder",
    "DemoEncoderGateway",
    "DemoPipeline",
    "DemoTracker",
    "DemoTrackIngestionRequest",
    "SyntheticMetadata",
    "build_demo_pipeline",
]
