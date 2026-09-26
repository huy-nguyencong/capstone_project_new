"""Stable, sanitized error taxonomy for AI worker boundaries."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from types import MappingProxyType
from typing import Any, Final


class AIStage(StrEnum):
    SOURCE = "SOURCE"
    SAMPLING = "SAMPLING"
    DETECTOR = "DETECTOR"
    TRACKER = "TRACKER"
    SELECTOR = "SELECTOR"
    IMAGE_ENCODER = "IMAGE_ENCODER"
    TEXT_ENCODER = "TEXT_ENCODER"
    STORAGE = "STORAGE"
    CANCELLATION = "CANCELLATION"
    RESOURCE = "RESOURCE"


class AIErrorCode(StrEnum):
    SOURCE_OPEN_FAILED = "source_open_failed"
    SOURCE_CONNECT_TIMEOUT = "source_connect_timeout"
    SOURCE_AUTH_FAILED = "source_auth_failed"
    SOURCE_READ_FAILED = "source_read_failed"
    SOURCE_READ_TIMEOUT = "source_read_timeout"
    SOURCE_STREAM_ENDED = "source_stream_ended"
    SOURCE_INVALID_FRAME = "source_invalid_frame"
    SAMPLING_INVALID_CONFIG = "sampling_invalid_config"
    SAMPLING_TIMELINE_INVALID = "sampling_timeline_invalid"
    DETECTOR_UNAVAILABLE = "detector_unavailable"
    DETECTOR_TIMEOUT = "detector_timeout"
    DETECTOR_INFERENCE_FAILED = "detector_inference_failed"
    DETECTOR_OUTPUT_INVALID = "detector_output_invalid"
    TRACKER_INFERENCE_FAILED = "tracker_inference_failed"
    TRACKER_OUTPUT_INVALID = "tracker_output_invalid"
    SELECTOR_FAILED = "selector_failed"
    SELECTOR_NO_REPRESENTATIVE = "selector_no_representative"
    IMAGE_ENCODER_UNAVAILABLE = "image_encoder_unavailable"
    IMAGE_ENCODER_INFERENCE_FAILED = "image_encoder_inference_failed"
    IMAGE_ENCODER_OUTPUT_INVALID = "image_encoder_output_invalid"
    TEXT_ENCODER_UNAVAILABLE = "text_encoder_unavailable"
    TEXT_ENCODER_INFERENCE_FAILED = "text_encoder_inference_failed"
    TEXT_ENCODER_OUTPUT_INVALID = "text_encoder_output_invalid"
    STORAGE_UNAVAILABLE = "storage_unavailable"
    STORAGE_CONFLICT = "storage_conflict"
    STORAGE_PUBLISH_FAILED = "storage_publish_failed"
    CANCELLED = "cancelled"
    RESOURCE_EXHAUSTED = "resource_exhausted"
    DEVICE_UNAVAILABLE = "device_unavailable"


@dataclass(frozen=True, slots=True)
class ErrorPolicy:
    stage: AIStage
    retryable: bool
    public_message: str


_POLICIES: Final = MappingProxyType(
    {
        AIErrorCode.SOURCE_OPEN_FAILED: ErrorPolicy(
            AIStage.SOURCE, True, "The frame source could not be opened."
        ),
        AIErrorCode.SOURCE_CONNECT_TIMEOUT: ErrorPolicy(
            AIStage.SOURCE, True, "The frame source connection timed out."
        ),
        AIErrorCode.SOURCE_AUTH_FAILED: ErrorPolicy(
            AIStage.SOURCE, False, "The frame source rejected its credentials."
        ),
        AIErrorCode.SOURCE_READ_FAILED: ErrorPolicy(
            AIStage.SOURCE, True, "The frame source could not be read."
        ),
        AIErrorCode.SOURCE_READ_TIMEOUT: ErrorPolicy(
            AIStage.SOURCE, True, "The frame source read timed out."
        ),
        AIErrorCode.SOURCE_STREAM_ENDED: ErrorPolicy(
            AIStage.SOURCE, True, "The live frame source ended unexpectedly."
        ),
        AIErrorCode.SOURCE_INVALID_FRAME: ErrorPolicy(
            AIStage.SOURCE, False, "The frame source returned invalid data."
        ),
        AIErrorCode.SAMPLING_INVALID_CONFIG: ErrorPolicy(
            AIStage.SAMPLING, False, "The frame sampling configuration is invalid."
        ),
        AIErrorCode.SAMPLING_TIMELINE_INVALID: ErrorPolicy(
            AIStage.SAMPLING, False, "The source timeline is invalid."
        ),
        AIErrorCode.DETECTOR_UNAVAILABLE: ErrorPolicy(
            AIStage.DETECTOR, True, "The detector is temporarily unavailable."
        ),
        AIErrorCode.DETECTOR_TIMEOUT: ErrorPolicy(
            AIStage.DETECTOR, True, "Person detection timed out."
        ),
        AIErrorCode.DETECTOR_INFERENCE_FAILED: ErrorPolicy(
            AIStage.DETECTOR, True, "Person detection failed."
        ),
        AIErrorCode.DETECTOR_OUTPUT_INVALID: ErrorPolicy(
            AIStage.DETECTOR, False, "The detector returned invalid output."
        ),
        AIErrorCode.TRACKER_INFERENCE_FAILED: ErrorPolicy(
            AIStage.TRACKER, True, "Person tracking failed."
        ),
        AIErrorCode.TRACKER_OUTPUT_INVALID: ErrorPolicy(
            AIStage.TRACKER, False, "The tracker returned invalid output."
        ),
        AIErrorCode.SELECTOR_FAILED: ErrorPolicy(
            AIStage.SELECTOR, False, "Representative-frame selection failed."
        ),
        AIErrorCode.SELECTOR_NO_REPRESENTATIVE: ErrorPolicy(
            AIStage.SELECTOR, False, "No valid representative frame was available."
        ),
        AIErrorCode.IMAGE_ENCODER_UNAVAILABLE: ErrorPolicy(
            AIStage.IMAGE_ENCODER, True, "The image encoder is temporarily unavailable."
        ),
        AIErrorCode.IMAGE_ENCODER_INFERENCE_FAILED: ErrorPolicy(
            AIStage.IMAGE_ENCODER, True, "Image encoding failed."
        ),
        AIErrorCode.IMAGE_ENCODER_OUTPUT_INVALID: ErrorPolicy(
            AIStage.IMAGE_ENCODER, False, "The image encoder returned invalid output."
        ),
        AIErrorCode.TEXT_ENCODER_UNAVAILABLE: ErrorPolicy(
            AIStage.TEXT_ENCODER, True, "The text encoder is temporarily unavailable."
        ),
        AIErrorCode.TEXT_ENCODER_INFERENCE_FAILED: ErrorPolicy(
            AIStage.TEXT_ENCODER, True, "Text encoding failed."
        ),
        AIErrorCode.TEXT_ENCODER_OUTPUT_INVALID: ErrorPolicy(
            AIStage.TEXT_ENCODER, False, "The text encoder returned invalid output."
        ),
        AIErrorCode.STORAGE_UNAVAILABLE: ErrorPolicy(
            AIStage.STORAGE, True, "Track storage is temporarily unavailable."
        ),
        AIErrorCode.STORAGE_CONFLICT: ErrorPolicy(
            AIStage.STORAGE, False, "Track publication conflicted with existing data."
        ),
        AIErrorCode.STORAGE_PUBLISH_FAILED: ErrorPolicy(
            AIStage.STORAGE, True, "Track publication failed."
        ),
        AIErrorCode.CANCELLED: ErrorPolicy(
            AIStage.CANCELLATION, False, "Processing was cancelled."
        ),
        AIErrorCode.RESOURCE_EXHAUSTED: ErrorPolicy(
            AIStage.RESOURCE, False, "The worker resource limit was exceeded."
        ),
        AIErrorCode.DEVICE_UNAVAILABLE: ErrorPolicy(
            AIStage.RESOURCE, True, "The configured inference device is unavailable."
        ),
    }
)


def error_policy(code: AIErrorCode) -> ErrorPolicy:
    if not isinstance(code, AIErrorCode):
        raise ValueError("code must be an AIErrorCode value.")
    return _POLICIES[code]


class AIWorkerError(RuntimeError):
    """An internal exception with a safe, stable public representation."""

    def __init__(
        self,
        code: AIErrorCode,
        *,
        internal_detail: str | None = None,
        cause: BaseException | None = None,
    ) -> None:
        policy = error_policy(code)
        super().__init__(policy.public_message)
        self.code = code
        self.stage = policy.stage
        self.retryable = policy.retryable
        self.internal_detail = internal_detail
        if cause is not None:
            self.__cause__ = cause

    def to_public_dict(self) -> dict[str, Any]:
        """Serialize without internal exception text, paths, credentials, or payloads."""

        return {
            "code": self.code.value,
            "stage": self.stage.value,
            "retryable": self.retryable,
            "message": str(self),
        }
