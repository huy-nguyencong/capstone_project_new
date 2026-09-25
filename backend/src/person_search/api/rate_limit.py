from __future__ import annotations

import math
import threading
import time
from collections.abc import Callable
from functools import wraps
from typing import Any, TypeVar, cast

from flask import current_app, g, request

from person_search.api.errors import ApiError

RouteT = TypeVar("RouteT", bound=Callable[..., Any])


class FixedWindowLimiter:
    def __init__(self, clock: Callable[[], float] = time.monotonic) -> None:
        self._clock = clock
        self._lock = threading.Lock()
        self._windows: dict[tuple[str, str], tuple[float, int]] = {}

    def hit(self, bucket: str, key: str, limit: int, window: int) -> float | None:
        now = self._clock()
        with self._lock:
            if len(self._windows) > 10_000:
                self._windows = {k: v for k, v in self._windows.items() if now - v[0] < window}
            started, count = self._windows.get((bucket, key), (now, 0))
            if now - started >= window:
                started, count = now, 0
            if count >= limit:
                return window - (now - started)
            self._windows[(bucket, key)] = (started, count + 1)
            return None


def limiter() -> FixedWindowLimiter:
    return cast(FixedWindowLimiter, current_app.extensions["person_search.rate_limiter"])


def client_address() -> str:
    return request.remote_addr or "unknown"


def enforce(bucket: str, key: str) -> None:
    limits = current_app.config.get("RATE_LIMITS", {})
    if bucket not in limits:
        return
    limit, window = limits[bucket]
    retry_after = limiter().hit(bucket, key, limit, window)
    if retry_after is not None:
        g.retry_after = max(1, math.ceil(retry_after))
        raise ApiError(
            429,
            "rate_limited",
            "Bạn thao tác quá nhanh. Vui lòng thử lại sau ít phút.",
            details={"retry_after_seconds": g.retry_after},
        )


def rate_limited(bucket: str) -> Callable[[RouteT], RouteT]:
    def decorator(route: RouteT) -> RouteT:
        @wraps(route)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            actor = g.get("actor")
            enforce(bucket, str(actor.id) if actor is not None else client_address())
            return route(*args, **kwargs)

        return cast(RouteT, wrapper)

    return decorator
