"""
Bulkhead / concurrency limiter — protect the channel under sudden load spikes.

WHY
---
Server-driven UI multiplies POSTs (every click is an action). A traffic spike
or client bug can pile up concurrent dispatches and exhaust workers. A bulkhead
caps concurrent action executions and rejects excess with a retryable Result.

USAGE
-----
::

    from ux_channel.security.bulkhead import ConcurrencyLimiter, bulkhead_hook
    lim = ConcurrencyLimiter(max_in_flight=64)
    reg.before(bulkhead_hook(lim))

Or via Channel / factory ``max_in_flight=``.

"""

from __future__ import annotations

import threading
import time
from typing import Any, Callable, Optional

from ux_channel.protocol.types import Intent, Result


class ConcurrencyLimiter:
    """Process-local semaphore bulkhead with stats for load testing."""

    def __init__(self, max_in_flight: int = 64):
        if max_in_flight < 1:
            raise ValueError("max_in_flight must be >= 1")
        self.max_in_flight = max_in_flight
        self._sem = threading.BoundedSemaphore(max_in_flight)
        self._lock = threading.Lock()
        self.in_flight = 0
        self.peak_in_flight = 0
        self.accepted = 0
        self.rejected = 0
        self.completed = 0
        self.total_wait_ms = 0.0

    def try_acquire(self, *, timeout_s: float = 0.0) -> bool:
        ok = self._sem.acquire(blocking=timeout_s > 0, timeout=timeout_s if timeout_s > 0 else None)
        if not ok:
            with self._lock:
                self.rejected += 1
            return False
        with self._lock:
            self.in_flight += 1
            self.accepted += 1
            if self.in_flight > self.peak_in_flight:
                self.peak_in_flight = self.in_flight
        return True

    def release(self) -> None:
        with self._lock:
            self.in_flight = max(0, self.in_flight - 1)
            self.completed += 1
        self._sem.release()

    def stats(self) -> dict[str, Any]:
        with self._lock:
            return {
                "max_in_flight": self.max_in_flight,
                "in_flight": self.in_flight,
                "peak_in_flight": self.peak_in_flight,
                "accepted": self.accepted,
                "rejected": self.rejected,
                "completed": self.completed,
            }


def bulkhead_hook(
    limiter: ConcurrencyLimiter,
    *,
    timeout_s: float = 0.0,
) -> Callable[[Intent, dict[str, Any]], Optional[Result]]:
    """
    Before-hook: try to enter bulkhead. On reject → rate_limited Result.

    Release is attached via after-hook — install both with ``install_bulkhead``.
    """
    # Store tokens on intent.meta so after-hook can release even if handler fails
    def before(intent: Intent, args: dict[str, Any]) -> Optional[Result]:
        t0 = time.perf_counter()
        if not limiter.try_acquire(timeout_s=timeout_s):
            return Result.failure(
                "rate_limited",
                "channel at capacity — retry shortly",
                retryable=True,
                action=intent.action,
                request_id=intent.request_id,
            )
        wait_ms = (time.perf_counter() - t0) * 1000
        limiter.total_wait_ms += wait_ms
        meta = dict(intent.meta or {})
        meta["_bulkhead"] = True
        intent.meta = meta
        return None

    return before


def bulkhead_after_hook(
    limiter: ConcurrencyLimiter,
) -> Callable[[Intent, Result], Result]:
    def after(intent: Intent, result: Result) -> Result:
        if intent.meta and intent.meta.get("_bulkhead"):
            try:
                limiter.release()
            except Exception:
                import logging

                logging.getLogger("ux_channel.security.bulkhead").exception(
                    "bulkhead release failed — concurrency slot may leak"
                )
            # scrub internal flag from outward meta if present on result
        return result

    return after


def install_bulkhead(
    registry: Any,
    *,
    max_in_flight: int = 64,
    timeout_s: float = 0.0,
) -> ConcurrencyLimiter:
    """Attach before+after bulkhead hooks; return limiter for stats/load tests."""
    lim = ConcurrencyLimiter(max_in_flight=max_in_flight)
    registry.before(bulkhead_hook(lim, timeout_s=timeout_s))
    registry.after(bulkhead_after_hook(lim))
    # stash for introspection
    registry._bulkhead = lim  # type: ignore[attr-defined]
    return lim
