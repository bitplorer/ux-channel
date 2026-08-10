"""
Nonce / one-shot capability store.

Protocol + memory implementation; Redis in ux_channel.redis_extra.
"""

from __future__ import annotations

import threading
import time
from typing import Optional, Protocol


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
    """

    def __init__(self, *, max_keys: int = 100_000):
        self._seen: dict[str, float] = {}
        self._lock = threading.Lock()
        self.max_keys = max_keys

    def use_once(self, key: str, *, ttl_s: float = 3600) -> bool:
        now = time.monotonic()
        with self._lock:
            # purge expired only
            dead = [k for k, exp in self._seen.items() if exp < now]
            for k in dead:
                self._seen.pop(k, None)
            if key in self._seen and self._seen[key] >= now:
                return False
            if len(self._seen) >= self.max_keys:
                # fail closed — do not drop live nonces
                return False
            self._seen[key] = now + ttl_s
            return True
