"""
Nonce / one-shot capability store.

Protocol + memory implementation; Redis in ux_channel.redis_extra.
"""

from __future__ import annotations

import threading
import time
from typing import Protocol


class NonceStore(Protocol):
    def use_once(self, key: str, *, ttl_s: float = 3600) -> bool:
        """Return True if key was unused and is now consumed; False if replay."""
        ...


class MemoryNonceStore:
    """
    Process-local one-shot store. Not multi-worker safe.

    Eviction only removes **expired** keys. If the store is full of live keys,
    use_once returns False (fail closed) rather than dropping active nonces
    (which would allow once-cap replay).

    Expired keys are dropped lazily: a hit on an expired key is deleted
    immediately; a bounded sweep runs only when the map is at capacity.
    """

    _SWEEP = 256

    def __init__(self, *, max_keys: int = 100_000):
        self._seen: dict[str, float] = {}
        self._lock = threading.Lock()
        self.max_keys = max_keys

    def use_once(self, key: str, *, ttl_s: float = 3600) -> bool:
        now = time.monotonic()
        with self._lock:
            exp = self._seen.get(key)
            if exp is not None:
                if exp >= now:
                    return False
                del self._seen[key]
            if len(self._seen) >= self.max_keys:
                self._sweep_expired(now)
                if len(self._seen) >= self.max_keys:
                    return False
            self._seen[key] = now + ttl_s
            return True

    def _sweep_expired(self, now: float) -> None:
        dead: list[str] = []
        for i, (k, exp) in enumerate(self._seen.items()):
            if exp < now:
                dead.append(k)
            if i >= self._SWEEP and dead:
                break
        for k in dead:
            self._seen.pop(k, None)
