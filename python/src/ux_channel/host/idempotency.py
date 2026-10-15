"""Idempotency store for safe action retries."""
from __future__ import annotations
import threading
import time
import uuid
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
        # (expiry, body or _PENDING, claim token or "")
        self._data: dict[str, tuple[float, dict[str, Any], str]] = {}
        self._lock = threading.Lock()
        self.max_keys = max_keys

    def _evict_expired(self, now: float) -> None:
        dead = [k for k, item in self._data.items() if item[0] <= now]
        for k in dead:
            self._data.pop(k, None)

    def _live(self, key: str, now: float) -> Optional[dict[str, Any]]:
        item = self._data.get(key)
        if not item:
            return None
        exp, body = item[0], item[1]
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

    def claim(
        self, key: str, *, ttl_s: float = 3600
    ) -> tuple[str, Optional[dict[str, Any]], Optional[str]]:
        """Reserve ``key`` before the handler runs.

        Returns ``("hit", result, None)`` when a finished result is stored,
        ``("pending", None, None)`` when another call is in flight,
        or ``("reserved", None, token)`` when this call holds a new slot.
        The token is the only thing that may release the slot. A nested
        dispatch of the same key does not receive it.
        Raises ``IdempotencyCapacityError`` instead of dropping the save.
        """
        now = time.monotonic()
        with self._lock:
            self._evict_expired(now)
            body = self._live(key, now)
            if body is _PENDING:
                return "pending", None, None
            if body is not None:
                return "hit", body, None
            if len(self._data) >= self.max_keys:
                raise IdempotencyCapacityError(self.max_keys)
            token = uuid.uuid4().hex
            self._data[key] = (now + ttl_s, _PENDING, token)
            return "reserved", None, token

    def release(self, key: str, token: str | None = None) -> None:
        """Drop this call's in-flight reservation.

        A missing or different token does not touch the slot, so a nested
        dispatch cannot release the reservation its parent still owns.
        """
        if not token:
            return
        with self._lock:
            item = self._data.get(key)
            if not item or item[1] is not _PENDING:
                return
            owner = item[2] if len(item) > 2 else ""
            if owner != token:
                return
            self._data.pop(key, None)

    def set(self, key: str, result: dict[str, Any], *, ttl_s: float = 3600) -> None:
        now = time.monotonic()
        with self._lock:
            self._evict_expired(now)
            if key in self._data:
                self._data[key] = (now + ttl_s, result, "")
                return
            if len(self._data) >= self.max_keys:
                raise IdempotencyCapacityError(self.max_keys)
            self._data[key] = (now + ttl_s, result, "")
