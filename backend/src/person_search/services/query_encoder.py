from __future__ import annotations

import logging
import threading
from collections.abc import Callable, Sequence
from types import SimpleNamespace
from typing import Any

from person_search.services.searches import EncoderUnavailableError
from person_search.workers.errors import AIWorkerError

logger = logging.getLogger(__name__)


class InProcessQueryEncoder:
    def __init__(
        self,
        registry: Any,
        gateway_factory: Callable[[Any], Any],
    ) -> None:
        self.registry = registry
        self.gateway_factory = gateway_factory
        self._gateway: Any | None = None
        self._lock = threading.Lock()

    def _entry(self, version: str, dimension: int) -> Any:
        entry = self.registry.encoder
        if entry is None or not entry.available:
            raise EncoderUnavailableError("Production query encoder is not available.")
        if entry.version != version or entry.dimension != dimension:
            raise EncoderUnavailableError("Active encoder does not match the registry encoder.")
        return entry

    def _ensure(self, version: str, dimension: int) -> Any:
        entry = self._entry(version, dimension)
        if self._gateway is None:
            gateway = self.gateway_factory(SimpleNamespace(encoder=entry))
            try:
                gateway.open()
            except Exception as error:
                self._discard(gateway)
                logger.warning(
                    "query encoder load failed", extra={"error_type": type(error).__name__}
                )
                raise EncoderUnavailableError("Query encoder could not be loaded.") from error
            self._gateway = gateway
        return self._gateway

    @staticmethod
    def _discard(gateway: Any) -> None:
        try:
            gateway.close()
        except Exception:
            pass

    def _call(self, mode: str, payload: Any, version: str, dimension: int) -> Sequence[float]:
        with self._lock:
            gateway = self._ensure(version, dimension)
            try:
                method = gateway.image if mode == "image" else gateway.text
                return list(method(payload, version=version, dimension=dimension))
            except AIWorkerError as error:
                self._gateway = None
                self._discard(gateway)
                logger.warning(
                    "query encoder inference failed",
                    extra={"error_code": error.code.value, "mode": mode},
                )
                raise EncoderUnavailableError("Query encoder inference failed.") from error

    def image(self, content: bytes, *, version: str, dimension: int) -> Sequence[float]:
        return self._call("image", content, version, dimension)

    def text(self, text: str, *, version: str, dimension: int) -> Sequence[float]:
        return self._call("text", text, version, dimension)

    def image_tokens(self, content: bytes, *, version: str, dimension: int):
        return self._call_raw(lambda gateway: gateway.image_tokens, content, version, dimension)

    def itm_scores(self, text: str, tokens, *, version: str, dimension: int) -> Sequence[float]:
        return self._call_raw(
            lambda gateway: lambda value, **kw: gateway.itm_scores(value, tokens, **kw),
            text,
            version,
            dimension,
        )

    def _call_raw(self, method_of, payload: Any, version: str, dimension: int):
        with self._lock:
            gateway = self._ensure(version, dimension)
            try:
                return method_of(gateway)(payload, version=version, dimension=dimension)
            except AIWorkerError as error:
                self._gateway = None
                self._discard(gateway)
                logger.warning(
                    "query encoder re-ranking call failed",
                    extra={"error_code": error.code.value},
                )
                raise EncoderUnavailableError("Query encoder inference failed.") from error

    def close(self) -> None:
        with self._lock:
            gateway, self._gateway = self._gateway, None
        if gateway is not None:
            self._discard(gateway)
