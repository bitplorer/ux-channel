"""
State / draft stores — ephemeral UI memory, not your database.

First principles
----------------
``ch.draft`` holds **session/UI** values (counters, wizard step, flash).
Business truth lives in your DB; regions ``load`` it when painting.

Under concurrency use atomic APIs::

    ch.draft.change(key, lambda v: (v or 0) + 1)
    with ch.draft.edit(key) as slot: ...

Bare get+set races. See docs/COURSE.md and draft RMW notes in SECURITY_AUDIT.
"""
from __future__ import annotations

import copy
import threading
from dataclasses import dataclass, field
from typing import Any, Callable, Iterator, Mapping, Optional, Protocol, runtime_checkable

Mutator = Callable[[Any], Any]


class StateConflict(RuntimeError):
    """CAS commit failed — another writer changed the key during ``edit``."""


@runtime_checkable
class StateStore(Protocol):
    """Minimal durable-enough state port for channel regions / drafts."""

    def get(self, key: str, default: Any = None) -> Any: ...

    def set(self, key: str, value: Any) -> None: ...

    def delete(self, key: str) -> None: ...

    def change(self, key: str, mutator: Mutator, *, default: Any = None) -> Any:
        """Atomic transform under the store lock: ``new = mutator(current_or_default)``."""
        ...

    def merge(self, key: str, updates: Mapping[str, Any], *, default: Any = None) -> Any:
        """Atomic dict merge; return new mapping."""
        ...

    def edit(self, key: str, *, default: Any = None) -> "EditSlot":
        """Context manager: mutate ``slot.value``, CAS-commit on exit."""
        ...

    # --- aliases (stable) -------------------------------------------------
    def update(self, key: str, mutator: Mutator, *, default: Any = None) -> Any:
        """Alias of ``change``."""
        ...

    def patch(self, key: str, updates: Mapping[str, Any], *, default: Any = None) -> Any:
        """Alias of ``merge``."""
        ...

    def incr(self, key: str, delta: float = 1, *, default: float = 0) -> float:
        """Sugar: ``change(key, lambda n: n + delta)`` for numeric counters."""
        ...


@dataclass
class EditSlot:
    """
    Mutable view from ``edit(key)``.

    Sync::

        with store.edit("n", default=0) as slot:
            slot.value += 1

    Async (same CAS commit; works under asyncio handlers)::

        async with store.edit("n", default=0) as slot:
            slot.value += 1

    On successful exit, ``slot.value`` is CAS-written. If another writer
    changed the key since enter, raises ``StateConflict`` (retry the block).
    """

    key: str
    value: Any
    _store: Any = field(repr=False)
    _version: int = field(repr=False)
    _default: Any = field(repr=False, default=None)
    _committed: bool = field(default=False, repr=False)

    def __enter__(self) -> "EditSlot":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        if exc_type is not None:
            return None  # discard on error
        self._commit()
        return None

    async def __aenter__(self) -> "EditSlot":
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        if exc_type is not None:
            return None
        # Prefer async CAS when the store provides it (Redis); else sync.
        commit = getattr(self._store, "_acas_set", None)
        if commit is not None:
            await commit(self.key, self._version, self.value)
        else:
            self._commit()
        self._committed = True
        return None

    def _commit(self) -> None:
        self._store._cas_set(self.key, self._version, self.value)
        self._committed = True


class MemoryStateStore:
    """
    Process-local state (dev / single worker).

    Not shared across workers — use RedisStateStore or your DB in multi-worker prod.
    """

    def __init__(self) -> None:
        self._data: dict[str, Any] = {}
        self._ver: dict[str, int] = {}
        self._lock = threading.RLock()

    def get(self, key: str, default: Any = None) -> Any:
        with self._lock:
            if key not in self._data:
                return copy.deepcopy(default)
            return copy.deepcopy(self._data[key])

    def set(self, key: str, value: Any) -> None:
        with self._lock:
            self._data[key] = copy.deepcopy(value)
            self._ver[key] = self._ver.get(key, 0) + 1

    def delete(self, key: str) -> None:
        with self._lock:
            self._data.pop(key, None)
            self._ver.pop(key, None)

    def _snapshot(self, key: str, default: Any) -> tuple[Any, int]:
        with self._lock:
            if key in self._data:
                return copy.deepcopy(self._data[key]), self._ver.get(key, 0)
            return copy.deepcopy(default), self._ver.get(key, 0)

    def _cas_set(self, key: str, expected_ver: int, value: Any) -> None:
        with self._lock:
            cur = self._ver.get(key, 0)
            if cur != expected_ver:
                raise StateConflict(
                    f"state key {key!r} changed during edit "
                    f"(expected ver={expected_ver}, now={cur}); retry the with-block"
                )
            self._data[key] = copy.deepcopy(value)
            self._ver[key] = cur + 1

    def edit(self, key: str, *, default: Any = None) -> EditSlot:
        """
        Feels like get/set, but commits atomically::

            with ch.draft.edit("n", default=0) as slot:
                slot.value += 1

            async with ch.draft.edit("n", default=0) as slot:
                slot.value += 1

            with ch.draft.edit("form", default={}) as slot:
                slot.value["email"] = email

        Lock is **not** held during the block (safe for short pure logic).
        On concurrent writers, raises ``StateConflict`` — retry the block.
        """
        value, ver = self._snapshot(key, default)
        return EditSlot(key=key, value=value, _store=self, _version=ver, _default=default)

    def edit_retry(
        self,
        key: str,
        fn: Mutator,
        *,
        default: Any = None,
        retries: int = 32,
    ) -> Any:
        """
        Apply ``fn(current) -> new`` with CAS retries.

        Prefer ``change`` (holds lock) for pure transforms, or this when you
        want edit-style CAS with automatic retry under contention.
        """
        last: Exception | None = None
        for _ in range(max(1, int(retries))):
            try:
                with self.edit(key, default=default) as slot:
                    slot.value = fn(slot.value)
                return self.get(key, default)
            except StateConflict as exc:
                last = exc
                continue
        raise StateConflict(
            f"edit_retry exhausted for {key!r} after {retries} attempts"
        ) from last

    def change(self, key: str, mutator: Mutator, *, default: Any = None) -> Any:
        """Hold lock for entire ``mutator(current)`` → store (best for pure transforms)."""
        with self._lock:
            if key in self._data:
                current = copy.deepcopy(self._data[key])
            else:
                current = copy.deepcopy(default)
            new = mutator(current)
            self._data[key] = copy.deepcopy(new)
            self._ver[key] = self._ver.get(key, 0) + 1
            return copy.deepcopy(new)

    def merge(self, key: str, updates: Mapping[str, Any], *, default: Any = None) -> Any:
        def _mut(base: Any) -> Any:
            if base is None:
                base = {}
            if not isinstance(base, dict):
                raise TypeError(f"StateStore.merge expects dict at {key!r}")
            return {**base, **dict(updates)}

        return self.change(key, _mut, default=default if default is not None else {})

    def update(self, key: str, mutator: Mutator, *, default: Any = None) -> Any:
        return self.change(key, mutator, default=default)

    def patch(self, key: str, updates: Mapping[str, Any], *, default: Any = None) -> Any:
        return self.merge(key, updates, default=default)

    def incr(self, key: str, delta: float = 1, *, default: float = 0) -> float:
        """Optional sugar for counters — equivalent to change(+delta)."""

        def _mut(cur: Any) -> Any:
            base = default if cur is None else cur
            try:
                if isinstance(base, int) and isinstance(delta, int) and not isinstance(delta, bool):
                    return int(base) + int(delta)
                return float(base) + float(delta)
            except (TypeError, ValueError) as exc:
                raise TypeError(
                    f"StateStore.incr expects numeric at {key!r}, got {type(base).__name__}"
                ) from exc

        return self.change(key, _mut, default=default)  # type: ignore[return-value]

    def clear(self) -> None:
        with self._lock:
            self._data.clear()
            self._ver.clear()

    def keys(self) -> list[str]:
        with self._lock:
            return list(self._data.keys())


class NullStateStore:
    """Explicit no-op store (tests that must not persist)."""

    def get(self, key: str, default: Any = None) -> Any:
        return copy.deepcopy(default)

    def set(self, key: str, value: Any) -> None:
        return None

    def delete(self, key: str) -> None:
        return None

    def change(self, key: str, mutator: Mutator, *, default: Any = None) -> Any:
        return mutator(copy.deepcopy(default))

    def merge(self, key: str, updates: Mapping[str, Any], *, default: Any = None) -> Any:
        base = copy.deepcopy(default) if default is not None else {}
        if not isinstance(base, dict):
            base = {}
        return {**base, **dict(updates)}

    def edit(self, key: str, *, default: Any = None) -> EditSlot:
        # commits into nowhere — still yields a slot for API parity
        class _Null:
            def _cas_set(self, k, ver, value):
                return None

        return EditSlot(key=key, value=copy.deepcopy(default), _store=_Null(), _version=0)

    def update(self, key: str, mutator: Mutator, *, default: Any = None) -> Any:
        return self.change(key, mutator, default=default)

    def patch(self, key: str, updates: Mapping[str, Any], *, default: Any = None) -> Any:
        return self.merge(key, updates, default=default)

    def incr(self, key: str, delta: float = 1, *, default: float = 0) -> float:
        return self.change(key, lambda n: (n if n is not None else default) + delta, default=default)  # type: ignore[return-value, operator]
