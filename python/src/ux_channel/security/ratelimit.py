"""Rate limiting for action endpoints — protect heavy-lifting apps under load.

Server-driven UI multiplies POST traffic (every click is an action). Without
limits, a single client or bot can exhaust workers. This module provides:

  1. In-memory token bucket (single process / dev / sticky workers)
  2. RateLimiter protocol for Redis/multi-worker backends
  3. Registry before-hook…"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from typing import Any, Callable, Optional, Protocol

from ux_channel.protocol.types import Intent, Result


class RateLimiter(Protocol):
    """Backend-agnostic rate limit check. Return True if allowed."""

    def allow(self, key: str, *, cost: float = 1.0) -> bool:
        ...


@dataclass
class _Bucket:
    tokens: float
    updated: float


class MemoryRateLimiter:
    """
    Per-key token bucket in process memory.

    NOT shared across Gunicorn/Uvicorn workers — use RedisRateLimiter-shaped
    backends for multi-worker production (implement RateLimiter protocol).

    Thread-safe for threaded servers; asyncio single-thread also fine.
    """

    def __init__(
        self,
        *,
        rate_per_minute: float = 120.0,
        burst: float = 30.0,
        max_keys: int = 50_000,
    ):
        if rate_per_minute <= 0:
            raise ValueError("rate_per_minute must be positive")
        self.rate_per_sec = rate_per_minute / 60.0
        self.burst = float(burst)
        self.max_keys = max_keys
        self._buckets: dict[str, _Bucket] = {}
        self._lock = threading.Lock()

    def allow(self, key: str, *, cost: float = 1.0) -> bool:
        now = time.monotonic()
        with self._lock:
            if key not in self._buckets and len(self._buckets) >= self.max_keys:
                return False
            b = self._buckets.get(key)
            if b is None:
                b = _Bucket(tokens=self.burst, updated=now)
                self._buckets[key] = b
            elapsed = max(0.0, now - b.updated)
            b.tokens = min(self.burst, b.tokens + elapsed * self.rate_per_sec)
            b.updated = now
            if b.tokens >= cost:
                b.tokens -= cost
                return True
            return False


def rate_limit_hook(
    limiter: RateLimiter,
    *,
    key_fn: Optional[Callable[[Intent, dict[str, Any]], str]] = None,
) -> Callable[[Intent, dict[str, Any]], Optional[Result]]:
    """
    Build a registry before-hook that returns 429-style Result when limited.

    Default key is action name only — pass key_fn that includes user id / IP
    for real production (inject via args from a host wrapper).
    """

    def _key(intent: Intent, args: dict[str, Any]) -> str:
        if key_fn:
            return key_fn(intent, args)
        return f"action:{intent.action}"

    def hook(intent: Intent, args: dict[str, Any]) -> Optional[Result]:
        if limiter.allow(_key(intent, args)):
            return None
        return Result.failure(
            "rate_limited",
            "Too many requests — slow down and retry",
            retryable=True,  # type: ignore[call-arg]
        )

    # Result.failure doesn't take retryable on ErrorObject easily - fix via ops
    # Actually ErrorObject has retryable - need to fix failure() or set after
    def _retry_after_s() -> float:
        # Prefer 1 token refill interval when MemoryRateLimiter; else 5s default
        rps = getattr(limiter, "rate_per_sec", None)
        if isinstance(rps, (int, float)) and rps > 0:
            return max(1.0, round(1.0 / float(rps), 3))
        return 5.0

    def hook_fixed(intent: Intent, args: dict[str, Any]) -> Optional[Result]:
        if limiter.allow(_key(intent, args)):
            return None
        try:
            from ux_channel.security.security_events import emit_security

            emit_security(
                "rate_limited",
                action=getattr(intent, "action", "") or "",
                reason="rate limit",
                client=str(_key(intent, args)),
            )
        except Exception:
            pass
        ra = _retry_after_s()
        r = Result.failure(
            "rate_limited",
            "Too many requests — slow down and retry",
            retry_after=ra,
        )
        if r.error:
            r.error.retryable = True
        return r

    return hook_fixed


def client_ip_from_scope(scope_or_headers: Any, trusted_proxy: bool = False) -> str:
    """
    Best-effort client IP extraction for host-layer rate limits.

    If trusted_proxy is True, honor X-Forwarded-For first hop (only behind
    a known reverse proxy — never enable on open internet without proxy).
    """
    # headers: list of (bytes,bytes) or Mapping
    def _get(name: str) -> str:
        if hasattr(scope_or_headers, "get"):
            v = scope_or_headers.get(name) or scope_or_headers.get(name.lower())
            return str(v) if v else ""
        return ""

    if trusted_proxy:
        xff = _get("x-forwarded-for") or _get("X-Forwarded-For")
        if xff:
            return xff.split(",")[0].strip()
    return _get("x-real-ip") or "unknown"
