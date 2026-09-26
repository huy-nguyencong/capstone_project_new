"""Production candidate-model loading used before an AI config becomes active."""

from __future__ import annotations

import os
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any, Protocol

from person_search.ai.detectors import build_yolo_detector, load_detector_settings
from person_search.ai.encoders import (
    build_rasa_image_encoder,
    build_rasa_query_gateway,
    load_rasa_settings,
)
from person_search.ai.preflight import apply_resource_environment, load_resource_settings
from person_search.ai.registry import PipelineSelection
from person_search.ai.trackers import build_bytetrack


class ModelLifecycle(Protocol):
    def open(self) -> None: ...

    def close(self) -> None: ...


ComponentBuilder = Callable[[PipelineSelection], ModelLifecycle]


class ProductionModelCandidateLoader:
    """Open every candidate adapter and always close it in reverse order."""

    def __init__(self, builders: Sequence[ComponentBuilder]) -> None:
        if len(builders) != 3:
            raise ValueError("Candidate loader requires Detector, Tracker, and Encoder builders.")
        self._builders = tuple(builders)

    def __call__(self, config: Any, selection: PipelineSelection) -> None:
        del config
        components: list[ModelLifecycle] = []
        load_error: BaseException | None = None
        try:
            for build in self._builders:
                component = build(selection)
                components.append(component)
                component.open()
        except BaseException as error:
            load_error = error
        close_errors: list[BaseException] = []
        for component in reversed(components):
            try:
                component.close()
            except BaseException as error:
                close_errors.append(error)
        if load_error is not None:
            raise load_error
        if close_errors:
            raise close_errors[0]

    @classmethod
    def from_environment(
        cls,
        *,
        artifact_root: Path,
        config_root: Path,
    ) -> ProductionModelCandidateLoader:
        factory = ProductionComponentFactory.from_environment(
            artifact_root=artifact_root, config_root=config_root
        )
        return cls((factory.detector, factory.tracker, factory.image_encoder))


class ProductionComponentFactory:
    def __init__(
        self,
        *,
        artifact_root: Path,
        device: str,
        detector_settings: Any,
        rasa_settings: Any,
    ) -> None:
        self.artifact_root = artifact_root
        self.device = device
        self.detector_settings = detector_settings
        self.rasa_settings = rasa_settings

    @classmethod
    def from_environment(
        cls,
        *,
        artifact_root: Path,
        config_root: Path,
    ) -> ProductionComponentFactory:
        resource_settings = load_resource_settings(
            os.getenv("PERSON_SEARCH_AI_RESOURCE_CONFIG")
            or config_root / "ai_resources.json",
            os.getenv("PERSON_SEARCH_AI_RESOURCE_PROFILE", "local_cpu"),
        )
        apply_resource_environment(resource_settings)
        return cls(
            artifact_root=artifact_root,
            device="cuda" if resource_settings.device_preference.value == "cuda" else "cpu",
            detector_settings=load_detector_settings(
                os.getenv("PERSON_SEARCH_DETECTOR_CONFIG")
                or config_root / "ultralytics_yolo_detector.json"
            ),
            rasa_settings=load_rasa_settings(
                os.getenv("PERSON_SEARCH_RASA_CONFIG")
                or config_root / "rasa_cuhk_pedes_runtime.json"
            ),
        )

    def detector(self, selection: PipelineSelection):
        return build_yolo_detector(
            selection.detector,
            artifact_root=self.artifact_root,
            device=self.device,
            settings=self.detector_settings,
        )

    def tracker(self, selection: PipelineSelection):
        return build_bytetrack(
            selection.tracker,
            artifact_root=self.artifact_root,
            device=self.device,
        )

    def image_encoder(self, selection: PipelineSelection):
        return build_rasa_image_encoder(
            selection.encoder,
            artifact_root=self.artifact_root,
            runtime_settings=self.rasa_settings,
            device=self.device,
        )

    def query_gateway(self, selection: PipelineSelection):
        return build_rasa_query_gateway(
            selection.encoder,
            artifact_root=self.artifact_root,
            runtime_settings=self.rasa_settings,
            device=self.device,
        )
