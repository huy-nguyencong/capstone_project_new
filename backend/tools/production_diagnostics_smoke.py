from __future__ import annotations

import argparse
import json
import uuid
from pathlib import Path
from types import SimpleNamespace

from person_search.ai.config_loader import ProductionComponentFactory
from person_search.ai.registry import load_registry
from person_search.services.camera_runtime import CameraRuntime
from person_search.services.diagnostics import (
    DiagnosticSettings,
    ProductionDiagnostics,
    camera_source_opener,
)
from person_search.services.monitoring import overall
from person_search.storage.postgres.models import CameraStatus


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run UC-07 diagnostics with production adapters on a real video sample."
    )
    parser.add_argument("--registry", type=Path, required=True)
    parser.add_argument("--artifact-root", type=Path, required=True)
    parser.add_argument("--config-root", type=Path, required=True)
    parser.add_argument("--video", type=Path, required=True)
    parser.add_argument("--timeout", type=float, default=300.0)
    args = parser.parse_args()
    registry = load_registry(
        args.registry,
        artifact_root=args.artifact_root,
        preflight_available={"yolo11n_coco", "bytetrack_v1", "rasa_cuhk_pedes_v1"},
    )
    selection = registry.resolve("yolo11n_coco", "bytetrack_v1")
    config = SimpleNamespace(
        detector_name=selection.detector.id,
        detector_version=selection.detector.version,
        tracker_name=selection.tracker.id,
        tracker_version=selection.tracker.version,
        encoder_name=selection.encoder.id,
        encoder_version=selection.encoder.version,
        encoder_dimension=selection.encoder.dimension,
        checkpoint_sha256=selection.encoder.artifact.sha256,
    )
    settings = DiagnosticSettings(deadline_seconds=args.timeout)
    diagnostics = ProductionDiagnostics(
        registry,
        ProductionComponentFactory.from_environment(
            artifact_root=args.artifact_root, config_root=args.config_root
        ),
        camera_source_opener(
            CameraRuntime(), settings, sample_video=args.video.resolve()
        ),
        settings=settings,
    )
    camera = SimpleNamespace(
        id=uuid.uuid4(),
        status=CameraStatus.ACTIVE,
        ai_enabled=True,
        rtsp_url=None,
        rtsp_credentials=None,
    )
    pipeline = diagnostics.camera_pipeline(camera, config)
    search = diagnostics.search_components(config)
    report = {
        "camera_pipeline": {
            "overall": overall(pipeline).value,
            "steps": [step.as_dict() for step in pipeline],
        },
        "search_components": {
            "overall": overall(search).value,
            "steps": [step.as_dict() for step in search],
        },
    }
    # Keep the CLI portable when Windows inherits a legacy console code page.
    # The JSON remains lossless because non-ASCII text is emitted as escapes.
    print(json.dumps(report, ensure_ascii=True, indent=2))
    passed = all(
        section["overall"] == "SUCCESS" for section in report.values()
    )
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
