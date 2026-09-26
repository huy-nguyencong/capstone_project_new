"""Production detector adapters selected from the model registry."""

from person_search.ai.detectors.ultralytics import (
    DetectorMetrics,
    DetectorSettings,
    RawDetection,
    UltralyticsProcessBackend,
    YoloPersonDetector,
    build_yolo_detector,
    load_detector_settings,
)

__all__ = [
    "DetectorSettings",
    "DetectorMetrics",
    "RawDetection",
    "UltralyticsProcessBackend",
    "YoloPersonDetector",
    "build_yolo_detector",
    "load_detector_settings",
]
