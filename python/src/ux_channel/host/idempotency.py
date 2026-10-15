"""Idempotency store for safe action retries."""
from __future__ import annotations
import threading, time
from typing import Any, Optional, Protocol

# In-flight reservation. Not a stored Result. ``get`` hides it.
_PENDING: dict[str, Any] = {"__ux_idem_pending__": True}


class IdempotencyCapacityError(RuntimeError):
    """Raised when a new key cannot be stored without dropping a live one."""

    def __init__(self, max_keys: int) -> None:
        super().__init__(f"idempotency store is full (max {max_keys} keys)")
        self.max_keys = max_keys


class IdempotencyStore(Protocol):
    def get(self, key: str) -> Optional[dict[str, Any]]: ...
    def set(self, key: str, result: dict[str, Any], *, ttl_s: float = 3600) -> None: ...


class MemoryIdempotencyStore:
    def __init__(self, *, max_keys: int = 50_000):
        self._data: dict[str, tuple[float, dict[str, Any]]] = {}
        self._lock = threading.Lock()
        self.max_keys = max_keys

    def _evict_expired(self, now: float) -> None:
        dead = [k for k, (exp, _) in self._data.items() if exp <= now]
        for k in dead:
            self._data.pop(k, None)

    def _live(self, key: str, now: float) -> Optional[dict[str, Any]]:
        item = self._data.get(key)
        if not item:
            return None
        exp, body = item
        if exp <= now:
            self._data.pop(key, None)
            return None
        return body

    def get(self, key: str) -> Optional[dict[str, Any]]:
        now = time.monotonic()
        with self._lock:
            body = self._live(key, now)
            if body is None or body is _PENDING:
                return None
            return body

    def claim(self, key: str, *, ttl_s: float = 3600) -> tuple[str, Optional[dict[str, Any]]]:
        """Reserve ``key`` before the handler runs.

        Returns ``("hit", result)`` when a finished result is stored,
        ``("pending", None)`` when another call is in flight,
        or ``("reserved", None)`` when this call holds a new slot.
        Raises ``IdempotencyCapacityError`` instead of dropping the save.
        """
        now = time.monotonic()
        with self._lock:
            self._evict_expired(now)
            body = self._live(key, now)
            if body is _PENDING:
                return "pending", None
            if body is not None:
                return "hit", body
            if len(self._data) >= self.max_keys:
                raise IdempotencyCapacityError(self.max_keys)
            self._data[key] = (now + ttl_s, _PENDING)
            return "reserved", None

    def release(self, key: str) -> None:
        """Drop an in-flight reservation so a failed call can be retried."""
        with self._lock:
            item = self._data.get(key)
            if item and item[1] is _PENDING:
                self._data.pop(key, None)

    def set(self, key: str, result: dict[str, Any], *, ttl_s: float = 3600) -> None:
        now = time.monotonic()
        with self._lock:
            self._evict_expired(now)
            if key in self._data:
                self._data[key] = (now + ttl_s, result)
                return
            if len(self._data) >= self.max_keys:
                raise IdempotencyCapacityError(self.max_keys)
            self._data[key] = (now + ttl_s, result)
