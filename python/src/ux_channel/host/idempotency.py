"""Idempotency store for safe action retries."""
from __future__ import annotations
import threading, time
from typing import Any, Optional, Protocol
class IdempotencyStore(Protocol):
    def get(self, key: str) -> Optional[dict[str, Any]]: ...
    def set(self, key: str, result: dict[str, Any], *, ttl_s: float = 3600) -> None: ...
class MemoryIdempotencyStore:
    def __init__(self, *, max_keys: int = 50_000):
        self._data: dict[str, tuple[float, dict[str, Any]]] = {}
        self._lock = threading.Lock()
        self.max_keys = max_keys
    def get(self, key: str) -> Optional[dict[str, Any]]:
        now = time.monotonic()
        with self._lock:
            item = self._data.get(key)
            if not item: return None
            exp, body = item
            if exp < now:
                self._data.pop(key, None)
                return None
            return body
    def set(self, key: str, result: dict[str, Any], *, ttl_s: float = 3600) -> None:
        now = time.monotonic()
        with self._lock:
            for k in [k for k,(e,_) in self._data.items() if e < now]:
                self._data.pop(k, None)
            if key in self._data:
                self._data[key] = (now + ttl_s, result)
                return
            if len(self._data) >= self.max_keys:
                return
            self._data[key] = (now + ttl_s, result)
