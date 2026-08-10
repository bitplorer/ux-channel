"""
WebSocket connection / message rate limits (Wave 1).

In-process by default; Redis-backed when redis_url is set.
"""

from __future__ import annotations

import threading
import time
from collections import defaultdict
from typing import Any, DefaultDict, Optional, Tuple


class WsRateLimiter:
    """
    Fixed-window counters for:
      - connections per key (IP) per minute
      - messages per connection key per minute
    """

    def __init__(
        self,
        *,
        max_connect_per_minute: int = 60,
        max_messages_per_minute: int = 600,
        redis_url: Optional[str] = None,
        prefix: str = "uidch:wsrl:",
    ) -> None:
        self.max_connect = max(1, int(max_connect_per_minute))
        self.max_messages = max(1, int(max_messages_per_minute))
        self.prefix = prefix
        self._redis = None
        if redis_url:
            try:
                from ux_channel.redis_extra import _client

                self._redis = _client(redis_url)
            except Exception:
                self._redis = None
        self._lock = threading.Lock()
        self._connect: DefaultDict[str, list[float]] = defaultdict(list)
        self._msgs: DefaultDict[str, list[float]] = defaultdict(list)

    def _prune(self, arr: list[float], now: float) -> list[float]:
        cutoff = now - 60.0
        return [t for t in arr if t >= cutoff]

    def allow_connect(self, key: str) -> Tuple[bool, str]:
        key = key or "unknown"
        if self._redis is not None:
            return self._redis_allow(f"c:{key}", self.max_connect)
        now = time.time()
        with self._lock:
            arr = self._prune(self._connect[key], now)
            if len(arr) >= self.max_connect:
                self._connect[key] = arr
                return False, "ws connect rate limit"
            arr.append(now)
            self._connect[key] = arr
        return True, "ok"

    def allow_message(self, key: str) -> Tuple[bool, str]:
        key = key or "unknown"
        if self._redis is not None:
            return self._redis_allow(f"m:{key}", self.max_messages)
        now = time.time()
        with self._lock:
            arr = self._prune(self._msgs[key], now)
            if len(arr) >= self.max_messages:
                self._msgs[key] = arr
                return False, "ws message rate limit"
            arr.append(now)
            self._msgs[key] = arr
        return True, "ok"

    def _redis_allow(self, key: str, limit: int) -> Tuple[bool, str]:
        import time as _t

        window = int(_t.time() // 60)
        rkey = f"{self.prefix}{key}:{window}"
        redis = self._redis
        if redis is None:
            return True, "ok"
        n = redis.incr(rkey)
        if n == 1:
            redis.expire(rkey, 120)
        if n > limit:
            return False, "ws rate limit"
        return True, "ok"


_limiter: Optional[WsRateLimiter] = None
_lock = threading.Lock()


def get_ws_limiter() -> Optional[WsRateLimiter]:
    return _limiter


def set_ws_limiter(limiter: Optional[WsRateLimiter]) -> None:
    global _limiter
    with _lock:
        _limiter = limiter


def configure_ws_limiter_from_config(config: Any, *, redis_url: Optional[str] = None) -> WsRateLimiter:
    lim = WsRateLimiter(
        max_connect_per_minute=int(getattr(config, "ws_connect_per_minute", 60) or 60),
        max_messages_per_minute=int(getattr(config, "ws_messages_per_minute", 600) or 600),
        redis_url=redis_url,
    )
    set_ws_limiter(lim)
    return lim
