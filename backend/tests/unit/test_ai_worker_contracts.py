"""Contract and error-taxonomy tests for framework-neutral AI components."""

from __future__ import annotations

import math
import uuid
from datetime import UTC, datetime

import pytest
from PIL import Image

from person_search.storage.contracts import BoundingBoxPixels
from person_search.workers.contracts import (
    BundleArtifact,
    CompletedTrack,
    ComponentOutcome,
    ComponentStatus,
    Detection,
    EmbeddingVector,
    IdempotentCloseMixin,
    ModelLineage,
    PublishedState,
    PublishedTrack,
    QualityComponent,
    QualityFlag,
    RepresentativeCandidate,
    ResultBundleManifest,
    SampledFrame,
    SourceFrame,
    TrackState,
    TrackUpdate,
    public_contract_fields,
)
from person_search.workers.errors import AIErrorCode, AIStage, AIWorkerError, error_policy

pytestmark = [pytest.mark.unit, pytest.mark.contract]

SHA = "a" * 64


def lineage(name: str = "component") -> ModelLineage:
    return ModelLineage(name, "1.0.0", SHA)


def source_frame(*, timestamp_ms: int = 200) -> SourceFrame:
    image = Image.new("RGB", (64, 48), "navy")
    return SourceFrame(uuid.uuid4(), 5, timestamp_ms, image, 64, 48)


def bbox() -> BoundingBoxPixels:
    return BoundingBoxPixels(4, 5, 20, 30, 64, 48)


def candidate(*, timestamp_ms: int = 200) -> RepresentativeCandidate:
    return RepresentativeCandidate(
        source_frame(timestamp_ms=timestamp_ms),
        bbox(),
        (QualityComponent("sharpness", 0.8), QualityComponent("visibility", 0.9)),
        0.85,
    )


def test_frame_detection_and_track_update_validate_boundaries() -> None:
    frame = source_frame()
    sampled = SampledFrame(frame, sampling_interval=10, sample_sequence=2)
    detection = Detection(bbox(), 0, "person", 0.75, lineage("detector"))
    update = TrackUpdate(
        "local-7",
        frame.camera_id,
        detection.bbox,
        frame.source_frame_index,
        frame.source_timestamp_ms,
        TrackState.ACTIVE,
        lineage("tracker"),
    )

    assert sampled.image is frame.image
    assert update.source_timestamp_ms == 200
    assert detection.confidence == 0.75

    with pytest.raises(ValueError, match="dimensions"):
        SourceFrame(frame.camera_id, 0, 0, frame.image, 63, 48)
    with pytest.raises(ValueError, match="person class"):
        Detection(bbox(), 1, "car", 0.9, lineage("detector"))
    with pytest.raises(ValueError, match="between 0 and 1"):
        Detection(bbox(), 0, "person", 1.1, lineage("detector"))
    with pytest.raises(ValueError, match="positive"):
        BoundingBoxPixels(0, 0, 0, 10, 64, 48)


def test_completed_track_requires_ordered_source_timeline() -> None:
    representative = candidate(timestamp_ms=200)
    values = dict(
        camera_id=representative.frame.camera_id,
        processing_job_id=uuid.uuid4(),
        ai_config_version_id=uuid.uuid4(),
        local_track_id="local-1",
        source_started_at_ms=100,
        source_ended_at_ms=300,
        representative=representative,
        quality_flag=QualityFlag.ACCEPTED,
        sampling_interval=10,
        detector=lineage("detector"),
        tracker=lineage("tracker"),
        encoder=lineage("encoder"),
    )

    track = CompletedTrack(**values)
    assert track.representative.frame.source_timestamp_ms == 200

    with pytest.raises(ValueError, match="inside the track interval"):
        CompletedTrack(**{**values, "source_started_at_ms": 201})
    with pytest.raises(ValueError, match="track camera"):
        CompletedTrack(**{**values, "camera_id": uuid.uuid4()})


@pytest.mark.parametrize("bad_value", [math.nan, math.inf, -math.inf])
def test_embedding_rejects_non_finite_values(bad_value: float) -> None:
    with pytest.raises(ValueError, match="finite"):
        EmbeddingVector((1.0, bad_value), 2, False, lineage("encoder"))


def test_embedding_requires_dimension_and_normalization_contract() -> None:
    vector = EmbeddingVector((0.6, 0.8), 2, True, lineage("encoder"))
    assert vector.values == (0.6, 0.8)

    with pytest.raises(ValueError, match="length"):
        EmbeddingVector((1.0,), 2, False, lineage("encoder"))
    with pytest.raises(ValueError, match="L2 norm 1"):
        EmbeddingVector((1.0, 1.0), 2, True, lineage("encoder"))


def test_published_track_and_bundle_keep_cross_storage_identity_and_checksums() -> None:
    track_id = uuid.uuid4()
    published = PublishedTrack(
        track_id,
        f"tracks/v1/{track_id}/representative.jpg",
        str(track_id),
        track_id,
        PublishedState.READY,
    )
    artifact = BundleArtifact("tracks/one.json", SHA.upper(), 12)
    manifest = ResultBundleManifest(
        "person-search-result-bundle/v1",
        "b" * 64,
        10,
        lineage("detector"),
        lineage("tracker"),
        lineage("encoder"),
        (artifact,),
    )

    assert published.state is PublishedState.READY
    assert manifest.artifacts[0].sha256 == SHA
    with pytest.raises(ValueError, match="inside the result bundle"):
        BundleArtifact("../escape.json", SHA, 1)


def test_component_status_and_public_projection_exclude_sensitive_payloads() -> None:
    frame = source_frame()
    vector = EmbeddingVector((1.0, 0.0), 2, True, lineage("encoder"))
    status = ComponentStatus(
        "detector",
        ComponentOutcome.SUCCESS,
        12.5,
        "ok",
        datetime(2026, 9, 26, tzinfo=UTC),
    )

    frame_public = public_contract_fields(frame)
    vector_public = public_contract_fields(vector)
    assert status.latency_ms == 12.5
    assert "image" not in frame_public
    assert "values" not in vector_public
    with pytest.raises(ValueError, match="normalized to UTC"):
        ComponentStatus(
            "detector",
            ComponentOutcome.SUCCESS,
            0,
            "ok",
            datetime(2026, 9, 26),
        )


def test_close_mixin_is_idempotent_even_when_release_raises() -> None:
    class Component(IdempotentCloseMixin):
        calls = 0

        def _close(self) -> None:
            self.calls += 1
            raise RuntimeError("private device detail")

    component = Component()
    with pytest.raises(RuntimeError, match="private device detail"):
        component.close()
    component.close()

    assert component.closed is True
    assert component.calls == 1


def test_error_taxonomy_is_complete_and_public_serialization_is_sanitized() -> None:
    assert {code for code in AIErrorCode if error_policy(code)} == set(AIErrorCode)
    error = AIWorkerError(
        AIErrorCode.DETECTOR_INFERENCE_FAILED,
        internal_detail="rtsp://admin:password@private-camera/path",
        cause=RuntimeError("CUDA secret path"),
    )

    payload = error.to_public_dict()
    serialized = str(payload)
    assert payload == {
        "code": "detector_inference_failed",
        "stage": AIStage.DETECTOR.value,
        "retryable": True,
        "message": "Person detection failed.",
    }
    assert "password" not in serialized
    assert "CUDA" not in serialized


def test_error_retryability_is_code_specific_not_exception_type_guessing() -> None:
    assert error_policy(AIErrorCode.DEVICE_UNAVAILABLE).retryable is True
    assert error_policy(AIErrorCode.RESOURCE_EXHAUSTED).retryable is False
    assert error_policy(AIErrorCode.DETECTOR_OUTPUT_INVALID).retryable is False
    assert error_policy(AIErrorCode.CANCELLED).stage is AIStage.CANCELLATION
