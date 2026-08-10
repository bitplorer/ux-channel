"""Intent outbox — queue Intents when the channel/mesh cannot apply them yet.

CONSTITUTION
Offline / partition does **not** invent a second mutation door.
Queued items are still Intent-shaped (action + args + optional cap metadata)
and drain through the same registry / ``Workplace.dispatch`` / agents path.

    Mesh is down or claim expired → enqueue
    Link restored / claim refreshed → drain →…"""

from __future__ import annotations

from ux_channel.protocol import serde as _serde

import json
import threading
import time
import uuid
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Callable, Mapping, Optional, Protocol, Sequence

__all__ = [
    "OutboxStatus",
    "OutboxItem",
    "OutboxError",
    "IntentOutbox",
    "MemoryIntentOutbox",
    "RedisIntentOutbox",
    "drain_outbox",
    "attach_outbox",
    "get_outbox",
]


class OutboxError(ValueError):
    """Outbox policy or storage error."""


class OutboxStatus(str, Enum):
    """Lifecycle of a queued Intent-shaped job."""

    PENDING = "pending"
    DRAINING = "draining"
    DONE = "done"
    FAILED = "failed"
    DEAD = "dead"  # max retries exceeded


@dataclass
class OutboxItem:
    """One queued Intent-shaped job."""

    id: str
    action: str
    args: dict[str, Any] = field(default_factory=dict)
    room: str = ""
    peer_id: str = ""
    scopes: tuple[str, ...] = ()
    status: OutboxStatus = OutboxStatus.PENDING
    attempts: int = 0
    max_attempts: int = 8
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    last_error: Optional[str] = None
    result_ok: Optional[bool] = None
    idempotency_key: Optional[str] = None
    meta: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["status"] = self.status.value
        d["scopes"] = list(self.scopes)
        return d

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "OutboxItem":
        st = data.get("status", "pending")
        if not isinstance(st, OutboxStatus):
            st = OutboxStatus(str(st))
        return cls(
            id=str(data["id"]),
            action=str(data["action"]),
            args=dict(data.get("args") or {}),
            room=str(data.get("room") or ""),
            peer_id=str(data.get("peer_id") or ""),
            scopes=tuple(str(s) for s in (data.get("scopes") or ())),
            status=st,
            attempts=int(data.get("attempts") or 0),
            max_attempts=int(data.get("max_attempts") or 8),
            created_at=float(data.get("created_at") or time.time()),
            updated_at=float(data.get("updated_at") or time.time()),
            last_error=data.get("last_error"),
            result_ok=data.get("result_ok"),
            idempotency_key=data.get("idempotency_key"),
            meta=dict(data.get("meta") or {}),
        )


class IntentOutbox(Protocol):
    """Storage protocol for Intent-shaped offline jobs."""

    def enqueue(
        self,
        action: str,
        args: Optional[Mapping[str, Any]] = None,
        *,
        room: str = "",
        peer_id: str = "",
        scopes: Sequence[str] = (),
        idempotency_key: Optional[str] = None,
        max_attempts: int = 8,
        meta: Optional[Mapping[str, Any]] = None,
    ) -> OutboxItem: ...

    def get(self, item_id: str) -> Optional[OutboxItem]: ...

    def list(
        self,
        *,
        status: Optional[OutboxStatus] = None,
        limit: int = 100,
    ) -> list[OutboxItem]: ...

    def claim_batch(self, n: int = 10) -> list[OutboxItem]: ...

    def mark_done(self, item_id: str, *, ok: bool = True) -> None: ...

    def mark_failed(self, item_id: str, error: str) -> None: ...

    def pending_count(self) -> int: ...


class MemoryIntentOutbox:
    """Process-local outbox (dev / single worker)."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._items: dict[str, OutboxItem] = {}
        self._idem: dict[str, str] = {}

    def enqueue(
        self,
        action: str,
        args: Optional[Mapping[str, Any]] = None,
        *,
        room: str = "",
        peer_id: str = "",
        scopes: Sequence[str] = (),
        idempotency_key: Optional[str] = None,
        max_attempts: int = 8,
        meta: Optional[Mapping[str, Any]] = None,
    ) -> OutboxItem:
        with self._lock:
            if idempotency_key and idempotency_key in self._idem:
                existing = self._items.get(self._idem[idempotency_key])
                if existing is not None:
                    return existing
            item = OutboxItem(
                id="obx_" + uuid.uuid4().hex[:16],
                action=str(action),
                args=dict(args or {}),
                room=str(room or ""),
                peer_id=str(peer_id or ""),
                scopes=tuple(str(s) for s in scopes),
                max_attempts=int(max_attempts),
                idempotency_key=idempotency_key,
                meta=dict(meta or {}),
            )
            self._items[item.id] = item
            if idempotency_key:
                self._idem[idempotency_key] = item.id
            return item

    def get(self, item_id: str) -> Optional[OutboxItem]:
        with self._lock:
            return self._items.get(item_id)

    def list(
        self,
        *,
        status: Optional[OutboxStatus] = None,
        limit: int = 100,
    ) -> list[OutboxItem]:
        with self._lock:
            rows = list(self._items.values())
        if status is not None:
            rows = [r for r in rows if r.status is status]
        rows.sort(key=lambda r: r.created_at)
        return rows[: int(limit)]

    def claim_batch(self, n: int = 10) -> list[OutboxItem]:
        with self._lock:
            pending = [
                i
                for i in self._items.values()
                if i.status in (OutboxStatus.PENDING, OutboxStatus.FAILED)
                and i.attempts < i.max_attempts
            ]
            pending.sort(key=lambda r: r.created_at)
            out: list[OutboxItem] = []
            for item in pending[: int(n)]:
                item.status = OutboxStatus.DRAINING
                item.attempts += 1
                item.updated_at = time.time()
                out.append(item)
            return out

    def mark_done(self, item_id: str, *, ok: bool = True) -> None:
        with self._lock:
            item = self._items.get(item_id)
            if not item:
                return
            item.status = OutboxStatus.DONE
            item.result_ok = ok
            item.updated_at = time.time()
            item.last_error = None

    def mark_failed(self, item_id: str, error: str) -> None:
        with self._lock:
            item = self._items.get(item_id)
            if not item:
                return
            item.last_error = str(error)[:500]
            item.updated_at = time.time()
            if item.attempts >= item.max_attempts:
                item.status = OutboxStatus.DEAD
            else:
                item.status = OutboxStatus.FAILED

    def pending_count(self) -> int:
        with self._lock:
            return sum(
                1
                for i in self._items.values()
                if i.status in (OutboxStatus.PENDING, OutboxStatus.FAILED)
            )


class RedisIntentOutbox:
    """
    Redis-backed outbox for multi-worker drain.

    Keys: ``{prefix}item:{id}`` hash/json, ``{prefix}pending`` zset by created_at,
    ``{prefix}idem:{key}`` → id.
    """

    def __init__(self, redis_url: str | Any, *, prefix: str = "uidch:outbox:") -> None:
        from ux_channel.redis_extra import _client

        self.r = _client(redis_url)
        self.prefix = prefix

    def _item_key(self, item_id: str) -> str:
        return f"{self.prefix}item:{item_id}"

    def _save(self, item: OutboxItem) -> None:
        self.r.set(self._item_key(item.id), _serde.dumps(item.to_dict()))

    def enqueue(
        self,
        action: str,
        args: Optional[Mapping[str, Any]] = None,
        *,
        room: str = "",
        peer_id: str = "",
        scopes: Sequence[str] = (),
        idempotency_key: Optional[str] = None,
        max_attempts: int = 8,
        meta: Optional[Mapping[str, Any]] = None,
    ) -> OutboxItem:
        if idempotency_key:
            existing_id = self.r.get(f"{self.prefix}idem:{idempotency_key}")
            if existing_id:
                raw = self.r.get(self._item_key(existing_id.decode() if isinstance(existing_id, bytes) else existing_id))
                if raw:
                    data = _serde.loads(raw)
                    return OutboxItem.from_dict(data)
        item = OutboxItem(
            id="obx_" + uuid.uuid4().hex[:16],
            action=str(action),
            args=dict(args or {}),
            room=str(room or ""),
            peer_id=str(peer_id or ""),
            scopes=tuple(str(s) for s in scopes),
            max_attempts=int(max_attempts),
            idempotency_key=idempotency_key,
            meta=dict(meta or {}),
        )
        self._save(item)
        self.r.zadd(f"{self.prefix}pending", {item.id: item.created_at})
        if idempotency_key:
            self.r.set(f"{self.prefix}idem:{idempotency_key}", item.id)
        return item

    def get(self, item_id: str) -> Optional[OutboxItem]:
        raw = self.r.get(self._item_key(item_id))
        if not raw:
            return None
        return OutboxItem.from_dict(_serde.loads(raw))

    def list(
        self,
        *,
        status: Optional[OutboxStatus] = None,
        limit: int = 100,
    ) -> list[OutboxItem]:
        ids = self.r.zrange(f"{self.prefix}pending", 0, max(0, int(limit) * 3 - 1))
        rows: list[OutboxItem] = []
        for i in ids:
            iid = i.decode() if isinstance(i, bytes) else str(i)
            item = self.get(iid)
            if item is None:
                continue
            if status is not None and item.status is not status:
                continue
            rows.append(item)
            if len(rows) >= int(limit):
                break
        return rows

    def claim_batch(self, n: int = 10) -> list[OutboxItem]:
        # Simple claim: read pending, mark draining (race-tolerant enough for kit)
        out: list[OutboxItem] = []
        for item in self.list(limit=int(n) * 2):
            if item.status not in (OutboxStatus.PENDING, OutboxStatus.FAILED):
                continue
            if item.attempts >= item.max_attempts:
                continue
            item.status = OutboxStatus.DRAINING
            item.attempts += 1
            item.updated_at = time.time()
            self._save(item)
            out.append(item)
            if len(out) >= int(n):
                break
        return out

    def mark_done(self, item_id: str, *, ok: bool = True) -> None:
        item = self.get(item_id)
        if not item:
            return
        item.status = OutboxStatus.DONE
        item.result_ok = ok
        item.updated_at = time.time()
        item.last_error = None
        self._save(item)
        self.r.zrem(f"{self.prefix}pending", item_id)

    def mark_failed(self, item_id: str, error: str) -> None:
        item = self.get(item_id)
        if not item:
            return
        item.last_error = str(error)[:500]
        item.updated_at = time.time()
        if item.attempts >= item.max_attempts:
            item.status = OutboxStatus.DEAD
            self.r.zrem(f"{self.prefix}pending", item_id)
        else:
            item.status = OutboxStatus.FAILED
        self._save(item)

    def pending_count(self) -> int:
        return int(self.r.zcard(f"{self.prefix}pending") or 0)


def drain_outbox(
    outbox: IntentOutbox,
    dispatch: Callable[[str, Mapping[str, Any], OutboxItem], Any],
    *,
    batch: int = 20,
) -> dict[str, int]:
    """
    Claim a batch and call ``dispatch(action, args, item)``.

    ``dispatch`` should raise on failure; return value may be a Result
    (``.ok`` checked when present).
    """
    stats = {"claimed": 0, "done": 0, "failed": 0}
    items = outbox.claim_batch(batch)
    stats["claimed"] = len(items)
    for item in items:
        try:
            result = dispatch(item.action, item.args, item)
            ok = True
            if result is not None and hasattr(result, "ok"):
                ok = bool(getattr(result, "ok"))
            if ok:
                outbox.mark_done(item.id, ok=True)
                stats["done"] += 1
            else:
                err = getattr(result, "error", None)
                msg = str(err) if err else "result not ok"
                outbox.mark_failed(item.id, msg)
                stats["failed"] += 1
        except Exception as exc:
            outbox.mark_failed(item.id, f"{type(exc).__name__}: {exc}")
            stats["failed"] += 1
    return stats


def attach_outbox(channel: Any, outbox: Optional[IntentOutbox] = None) -> IntentOutbox:
    """
    Attach an outbox to ``channel`` (creates memory or Redis from config if omitted).

    Returns the outbox instance for enqueue/drain.
    """
    existing = getattr(channel, "_intent_outbox", None)
    if existing is not None and outbox is None:
        return existing  # type: ignore[return-value]
    box: IntentOutbox
    if outbox is not None:
        box = outbox
    else:
        redis_url = getattr(getattr(channel, "config", None), "redis_url", None)
        if redis_url:
            try:
                box = RedisIntentOutbox(redis_url)
            except Exception:
                box = MemoryIntentOutbox()
        else:
            box = MemoryIntentOutbox()
    channel._intent_outbox = box
    return box


def get_outbox(channel: Any) -> Optional[IntentOutbox]:
    """Return the outbox attached via ``attach_outbox``, if any."""
    return getattr(channel, "_intent_outbox", None)
