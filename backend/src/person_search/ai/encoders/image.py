"""Production RaSa image-encoding boundary for tracks and image queries."""

from __future__ import annotations

import math
import multiprocessing
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from multiprocessing.connection import Connection
from pathlib import Path
from typing import Any, Protocol

from PIL import Image

from person_search.ai.encoders.rasa import RasaRuntimeFactory, RasaRuntimeSettings
from person_search.ai.registry import EncoderEntry
from person_search.workers.contracts import CompletedTrack, EmbeddingVector, ModelLineage
from person_search.workers.errors import AIErrorCode, AIWorkerError


@dataclass(frozen=True, slots=True)
class ImageEncoderSettings:
    inference_timeout_seconds: float = 120.0
    load_timeout_seconds: float = 300.0
    max_pixels: int = 24_000_000
    max_dimension: int = 12_000

    def __post_init__(self) -> None:
        for name in ("inference_timeout_seconds", "load_timeout_seconds"):
            value = getattr(self, name)
            if (
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or not math.isfinite(value)
                or value <= 0
            ):
                raise ValueError(f"{name} must be a positive finite number.")
        for name in ("max_pixels", "max_dimension"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int) or value < 1:
                raise ValueError(f"{name} must be a positive integer.")


@dataclass(frozen=True, slots=True)
class ImageEncoderMetrics:
    inference_count: int
    last_latency_ms: float | None


class ImageEncoderBackend(Protocol):
    def open(self) -> None: ...

    def encode(self, image: Image.Image, *, timeout_seconds: float) -> Sequence[float]: ...

    def close(self) -> None: ...


def _rasa_image_child(
    connection: Connection,
    entry: EncoderEntry,
    artifact_root: str,
    runtime_settings: RasaRuntimeSettings,
    device: str,
) -> None:
    try:
        runtime = RasaRuntimeFactory(
            entry,
            artifact_root=artifact_root,
            settings=runtime_settings,
            device=device,
        ).load()
        connection.send(("ready", None))
    except BaseException:
        connection.send(("load_error", None))
        connection.close()
        return
    try:
        while True:
            command, payload = connection.recv()
            if command == "close":
                return
            if command != "encode" or not isinstance(payload, Image.Image):
                connection.send(("inference_error", None))
                continue
            try:
                tensor = runtime.image_embedding(payload)
                connection.send(("ok", tensor.detach().cpu().reshape(-1).tolist()))
            except BaseException:
                connection.send(("inference_error", None))
            finally:
                payload.close()
    except (EOFError, BrokenPipeError):
        return
    finally:
        connection.close()


class RasaImageProcessBackend:
    """Keep model/tensor state in a process that can be killed after a timeout."""

    def __init__(
        self,
        entry: EncoderEntry,
        *,
        artifact_root: str | Path,
        runtime_settings: RasaRuntimeSettings,
        device: str,
        settings: ImageEncoderSettings,
        context_factory: Callable[[str], Any] = multiprocessing.get_context,
    ) -> None:
        self.entry = entry
        self.artifact_root = str(Path(artifact_root).resolve())
        self.runtime_settings = runtime_settings
        self.device = device
        self.settings = settings
        self._context_factory = context_factory
        self._connection: Connection | None = None
        self._process: Any | None = None

    def open(self) -> None:
        if self._process is not None:
            raise RuntimeError("Image encoder backend is already open.")
        context = self._context_factory("spawn")
        parent, child = context.Pipe()
        process = context.Process(
            target=_rasa_image_child,
            args=(
                child,
                self.entry,
                self.artifact_root,
                self.runtime_settings,
                self.device,
            ),
            daemon=True,
        )
        process.start()
        child.close()
        self._connection, self._process = parent, process
        if not parent.poll(self.settings.load_timeout_seconds):
            self.close()
            raise TimeoutError("RaSa image encoder load timed out.")
        status, _ = parent.recv()
        if status != "ready":
            self.close()
            raise RuntimeError("RaSa image encoder could not be loaded.")

    def encode(self, image: Image.Image, *, timeout_seconds: float) -> Sequence[float]:
        if self._connection is None or self._process is None or not self._process.is_alive():
            raise RuntimeError("RaSa image encoder backend is unavailable.")
        self._connection.send(("encode", image.copy()))
        if not self._connection.poll(timeout_seconds):
            self.close()
            raise TimeoutError("RaSa image inference timed out.")
        status, payload = self._connection.recv()
        if status != "ok" or not isinstance(payload, list):
            raise RuntimeError("RaSa image inference failed.")
        return payload

    def close(self) -> None:
        connection, self._connection = self._connection, None
        process, self._process = self._process, None
        if connection is not None:
            try:
                if process is not None and process.is_alive():
                    connection.send(("close", None))
            except (BrokenPipeError, EOFError, OSError):
                pass
            connection.close()
        if process is not None:
            process.join(timeout=2)
            if process.is_alive():
                process.terminate()
                process.join(timeout=5)
            if process.is_alive():
                process.kill()
                process.join()
            process.close()


class RasaImageEncoder:
    """Validate images and RaSa output at the shared track/query boundary."""

    def __init__(
        self,
        backend: ImageEncoderBackend,
        *,
        lineage: ModelLineage,
        dimension: int,
        settings: ImageEncoderSettings | None = None,
        clock: Callable[[], float] = time.perf_counter,
    ) -> None:
        self._backend = backend
        self.lineage = lineage
        self.dimension = dimension
        self.settings = settings or ImageEncoderSettings()
        self._clock = clock
        self._opened = False
        self._closed = False
        self._inference_count = 0
        self._last_latency_ms: float | None = None

    @property
    def metrics(self) -> ImageEncoderMetrics:
        return ImageEncoderMetrics(self._inference_count, self._last_latency_ms)

    def open(self) -> None:
        if self._opened or self._closed:
            raise RuntimeError("Image encoder instances are one-shot.")
        try:
            self._backend.open()
        except Exception as exc:
            self.close()
            raise AIWorkerError(AIErrorCode.IMAGE_ENCODER_UNAVAILABLE, cause=exc) from exc
        self._opened = True

    def encode(self, crop: Image.Image) -> EmbeddingVector:
        if not self._opened or self._closed:
            raise RuntimeError("Image encoder must be open before inference.")
        self._validate_image(crop)
        started = self._clock()
        try:
            raw = self._backend.encode(
                crop, timeout_seconds=self.settings.inference_timeout_seconds
            )
        except Exception as exc:
            self.close()
            raise AIWorkerError(AIErrorCode.IMAGE_ENCODER_INFERENCE_FAILED, cause=exc) from exc
        finally:
            self._inference_count += 1
            self._last_latency_ms = max(0.0, (self._clock() - started) * 1000)
        try:
            return EmbeddingVector(tuple(raw), self.dimension, True, self.lineage)
        except (TypeError, ValueError) as exc:
            self.close()
            raise AIWorkerError(AIErrorCode.IMAGE_ENCODER_OUTPUT_INVALID, cause=exc) from exc

    def _validate_image(self, image: Image.Image) -> None:
        if not isinstance(image, Image.Image):
            raise TypeError("Image encoder accepts PIL images only.")
        width, height = image.size
        if width < 1 or height < 1:
            raise ValueError("Image dimensions must be positive.")
        if (
            width > self.settings.max_dimension
            or height > self.settings.max_dimension
            or width * height > self.settings.max_pixels
        ):
            raise ValueError("Image dimensions exceed the inference limit.")
        if image.mode not in {"1", "L", "LA", "P", "RGB", "RGBA", "CMYK", "YCbCr"}:
            raise ValueError("Image channel layout is unsupported.")

    def close(self) -> None:
        if self._closed:
            return
        try:
            self._backend.close()
        finally:
            self._closed = True


class RasaTrackImageEncoder:
    """Crop exactly the persisted representative frame+bbox and encode it transiently."""

    def __init__(self, encoder: RasaImageEncoder) -> None:
        self.encoder = encoder

    def encode(self, track: CompletedTrack) -> EmbeddingVector:
        if not isinstance(track, CompletedTrack):
            raise TypeError("Track image encoding requires a CompletedTrack.")
        if track.encoder != self.encoder.lineage:
            raise ValueError("Track encoder lineage does not match the active image encoder.")
        bbox = track.representative.bbox
        crop = track.representative.frame.image.crop(
            (bbox.x, bbox.y, bbox.x + bbox.width, bbox.y + bbox.height)
        )
        try:
            return self.encoder.encode(crop)
        finally:
            crop.close()


class RasaImageQueryGateway:
    """Use the same encoder for uploaded query images without retaining raw bytes."""

    def __init__(self, encoder: RasaImageEncoder) -> None:
        self.encoder = encoder

    def image(self, content: bytes, *, version: str, dimension: int) -> Sequence[float]:
        if version != self.encoder.lineage.version or dimension != self.encoder.dimension:
            raise ValueError("Query encoder metadata does not match the active vector space.")
        from person_search.services.searches import decode_query_image

        image = decode_query_image(content)
        try:
            return self.encoder.encode(image).values
        finally:
            image.close()


def build_rasa_image_encoder(
    entry: EncoderEntry,
    *,
    artifact_root: str | Path,
    runtime_settings: RasaRuntimeSettings,
    device: str = "cpu",
    settings: ImageEncoderSettings | None = None,
    backend_factory: Callable[..., ImageEncoderBackend] = RasaImageProcessBackend,
) -> RasaImageEncoder:
    """Build a production adapter only after the AIW-13 runtime guard passes."""

    # The factory owns all artifact/checksum/device/preprocessing validation.
    RasaRuntimeFactory(
        entry,
        artifact_root=artifact_root,
        settings=runtime_settings,
        device=device,
    )
    selected = settings or ImageEncoderSettings()
    backend = backend_factory(
        entry,
        artifact_root=artifact_root,
        runtime_settings=runtime_settings,
        device=device,
        settings=selected,
    )
    return RasaImageEncoder(
        backend,
        lineage=ModelLineage(entry.id, entry.version, entry.artifact.sha256),
        dimension=entry.dimension,
        settings=selected,
    )
