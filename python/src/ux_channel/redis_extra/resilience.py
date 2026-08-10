"""
Redis connection resilience — soft-fail, reconnect, circuit breaker.

Used by intent log, intent sync, and push backends so a Redis outage
degrades gracefully instead of taking down the control plane.
"""

from __future__ import annotations

import logging
import threading
import time
from typing import Any, Callable, Optional

logger = logging.getLogger("ux_channel.redis")

__all__ = [
    "RedisUnavailable",
    "ResilientRedis",
    "resilient_client",
    "with_redis",
]


class RedisUnavailable(RuntimeError):
    """Redis is down or circuit is open. Callers should soft-fail."""


class ResilientRedis:
    """
    Thin wrapper around a redis client (or URL).

    * ``execute(fn)`` — run ``fn(client)``; on connection errors open circuit
    * Auto-reconnect after ``cooldown_s``
    * ``ping()`` health check
    """

    def __init__(
        self,
        redis_url: str | Any,
        *,
        cooldown_s: float = 2.0,
        max_failures: int = 3,
        soft_fail: bool = True,
    ) -> None:
        self._url = redis_url
        self._cooldown = max(0.1, float(cooldown_s))
        self._max_failures = max(1, int(max_failures))
        self._soft_fail = soft_fail
        self._client: Any = None
        self._failures = 0
        self._open_until = 0.0
        self._lock = threading.RLock()

    def _connect(self) -> Any:
        from ux_channel.redis_extra import _client

        if not isinstance(self._url, str) and self._url is not None:
            # already a client (FakeRedis, etc.)
            return self._url
        return _client(self._url)

    def client(self) -> Any:
        with self._lock:
            if time.monotonic() < self._open_until:
                raise RedisUnavailable(
                    f"redis circuit open for {self._open_until - time.monotonic():.1f}s"
                )
            if self._client is None:
                try:
                    self._client = self._connect()
                    # cheap health
                    if hasattr(self._client, "ping"):
                        self._client.ping()
                    self._failures = 0
                except Exception as exc:
                    self._trip(exc)
                    raise RedisUnavailable(str(exc)) from exc
            return self._client

    def _trip(self, exc: BaseException) -> None:
        self._failures += 1
        self._client = None
        if self._failures >= self._max_failures:
            self._open_until = time.monotonic() + self._cooldown
            logger.warning(
                "redis circuit open failures=%s cooldown=%.1fs err=%s",
                self._failures,
                self._cooldown,
                exc,
            )
        else:
            logger.warning("redis error failures=%s err=%s", self._failures, exc)

    def execute(self, fn: Callable[[Any], Any], *, default: Any = None) -> Any:
        """Run ``fn(redis_client)``. Soft-fail → ``default`` when configured."""
        try:
            c = self.client()
            return fn(c)
        except RedisUnavailable:
            if self._soft_fail:
                return default
            raise
        except Exception as exc:
            # connection-ish errors
            name = type(exc).__name__.lower()
            msg = str(exc).lower()
            if any(
                x in name or x in msg
                for x in (
                    "connection",
                    "timeout",
                    "busyloading",
                    "readonly",
                    "clusterdown",
                    "moved",
                    "ask",
                    "tryagain",
                )
            ):
                with self._lock:
                    self._trip(exc)
                if self._soft_fail:
                    return default
                raise RedisUnavailable(str(exc)) from exc
            raise

    def ping(self) -> bool:
        try:
            c = self.client()
            if hasattr(c, "ping"):
                return bool(c.ping())
            return True
        except Exception:
            return False

    def close(self) -> None:
        with self._lock:
            c = self._client
            self._client = None
            try:
                if c is not None and hasattr(c, "close"):
                    c.close()
            except Exception:
                pass


def resilient_client(
    redis_url: str | Any,
    **kwargs: Any,
) -> ResilientRedis:
    return ResilientRedis(redis_url, **kwargs)


def with_redis(
    redis_url: str | Any,
    fn: Callable[[Any], Any],
    *,
    default: Any = None,
    soft_fail: bool = True,
) -> Any:
    """One-shot execute with resilience."""
    return ResilientRedis(redis_url, soft_fail=soft_fail).execute(fn, default=default)
