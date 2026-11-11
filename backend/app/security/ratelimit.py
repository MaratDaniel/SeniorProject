"""Sliding-window rate limiter.

It is per process: enough for one API process. With several processes the limits
multiply by the process count, so move the counters to Redis before scaling out.
Account lockout does not depend on this: it is counted in the database.
"""

import math
import time
from collections import deque

from app.errors import ApiError


class RateLimiter:
    def __init__(self, *, max_keys: int = 50_000) -> None:
        self._hits: dict[str, deque[float]] = {}
        self._max_keys = max_keys

    def hit(self, key: str, limit: int, window_seconds: float) -> float | None:
        """Record a hit. Returns the seconds to wait if the limit is exceeded, otherwise None."""
        now = time.monotonic()
        hits = self._hits.get(key)
        if hits is None:
            if len(self._hits) >= self._max_keys:
                self._prune(now, window_seconds)
            hits = self._hits[key] = deque()
        while hits and hits[0] <= now - window_seconds:
            hits.popleft()
        if len(hits) >= limit:
            return hits[0] + window_seconds - now
        hits.append(now)
        return None

    def check(self, key: str, limit: int, window_seconds: float) -> None:
        wait = self.hit(key, limit, window_seconds)
        if wait is not None:
            seconds = max(1, math.ceil(wait))
            raise ApiError(
                429,
                "rate_limited",
                "Too many attempts. Wait a moment and try again.",
                {"retry_after": seconds},
                headers={"Retry-After": str(seconds)},
            )

    def _prune(self, now: float, window_seconds: float) -> None:
        stale = [k for k, q in self._hits.items() if not q or q[-1] <= now - window_seconds]
        for key in stale:
            del self._hits[key]
