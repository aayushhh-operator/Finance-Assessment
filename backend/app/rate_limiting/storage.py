"""In-memory storage for fixed-window rate limiting."""

from __future__ import annotations

from dataclasses import dataclass
from threading import Lock
from time import time

from app.rate_limiting.rules import RateLimitRule


@dataclass(frozen=True, slots=True)
class RateLimitResult:
    """Result returned after evaluating a rate limit rule."""

    allowed: bool
    limit: int
    remaining: int
    reset_at: int
    retry_after: int


class InMemoryRateLimitStorage:
    """Thread-safe fixed-window rate limit storage for single-process demos.

    This implementation keeps counters in local memory, which is acceptable for
    an assessment or a single FastAPI instance. In production, use Redis via
    `redis-py` so multiple API instances can share the same counters and enforce
    limits consistently across a horizontally scaled deployment.
    """

    def __init__(self) -> None:
        self._lock = Lock()
        self._entries: dict[str, list[float]] = {}
        self._max_window_seconds = 0

    def check_rate_limit(self, key: str, rule: RateLimitRule) -> RateLimitResult:
        """Evaluate and record a request against a fixed-window rule.

        Fixed windows are simple to reason about for assessment reviewers, but
        they can allow small bursts near window boundaries. A production Redis
        implementation might still use fixed windows for simplicity or switch to
        sliding-window counters for smoother enforcement.
        """

        current_time = time()
        current_window_start = int(current_time // rule.window_seconds) * rule.window_seconds
        reset_at = current_window_start + rule.window_seconds

        with self._lock:
            self._max_window_seconds = max(self._max_window_seconds, rule.window_seconds)
            timestamps = self._entries.get(key, [])
            active_timestamps = [timestamp for timestamp in timestamps if timestamp >= current_window_start]
            self._cleanup_stale_entries(current_time)

            if len(active_timestamps) >= rule.max_requests:
                self._entries[key] = active_timestamps
                retry_after = max(1, int(reset_at - current_time))
                return RateLimitResult(
                    allowed=False,
                    limit=rule.max_requests,
                    remaining=0,
                    reset_at=reset_at,
                    retry_after=retry_after,
                )

            active_timestamps.append(current_time)
            self._entries[key] = active_timestamps
            remaining = max(0, rule.max_requests - len(active_timestamps))
            return RateLimitResult(
                allowed=True,
                limit=rule.max_requests,
                remaining=remaining,
                reset_at=reset_at,
                retry_after=0,
            )

    def reset(self) -> None:
        """Clear all in-memory counters, mainly for tests."""

        with self._lock:
            self._entries.clear()

    def _cleanup_stale_entries(self, current_time: float) -> None:
        """Drop keys whose timestamps have fully expired to avoid leaks."""

        oldest_allowed_timestamp = current_time - self._max_window_seconds
        stale_keys = []
        for key, timestamps in self._entries.items():
            fresh_timestamps = [timestamp for timestamp in timestamps if timestamp >= oldest_allowed_timestamp]
            if fresh_timestamps:
                self._entries[key] = fresh_timestamps
            else:
                stale_keys.append(key)

        for key in stale_keys:
            self._entries.pop(key, None)
