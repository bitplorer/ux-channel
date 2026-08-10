"""Idempotency store for safe action retries."""

from __future__ import annotations

import json
import threading
import time
from typing import Any, Optional, Protocol

from ux_channel.protocol.types import Result


class IdempotencyStore(Protocol):
    def get(self, key: str) -> Optional[dict[str, Any]]:
        ...

    def set(self, key: str, result: dict[str, Any], *, ttl_s: float = 3600) -> None:
        ...


class MemoryIdempotencyStore:
    def __init__(self, *, max_keys: int = 50_000):
        self._data: dict[str, tuple[float, dict[str, Any]]] = {}
        self._lock = threading.Lock()
        self.max_keys = max_keys

    def get(self, key: str) -> Optional[dict[str, Any]]:
        now = time.monotonic()
        with self._lock:
            item = self._data.get(key)
            if not item:
                return None
            exp, body = item
            if exp < now:
                self._data.pop(key, None)
                return None
            return body

    def set(self, key: str, result: dict[str, Any], *, ttl_s: float = 3600) -> None:
        now = time.monotonic()
        with self._lock:
            if len(self._data) >= self.max_keys:
                for k in list(self._data.keys())[: self.max_keys // 10]:
                    self._data.pop(k, None)
            self._data[key] = (now + ttl_s, result)
