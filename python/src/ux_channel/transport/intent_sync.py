"""
Real-time intent sync across workers (Redis pub/sub).

Complements ``IntentLog`` (durable list) with **live fan-out**:

* Worker A handles Intent → append log + publish sync message
* Worker B subscribers receive entry → optional local hooks (metrics, live morph)

Does not import ux-dom.
"""

from __future__ import annotations

from ux_channel.protocol import serde as _serde

import json
import logging
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Callable, List, Optional, Protocol

from ux_channel.protocol.types import Intent, Result

logger = logging.getLogger("ux_channel.transport.intent_sync")

__all__ = [
    "IntentSyncMessage",
    "IntentSyncBus",
    "MemoryIntentSyncBus",
    "RedisIntentSyncBus",
    "attach_intent_sync",
]

SyncHandler = Callable[["IntentSyncMessage"], None]


@dataclass
class IntentSyncMessage:
    """Wire payload for cross-worker intent awareness."""

    seq: int
    action: str
    ok: bool
    op_kinds: tuple[str, ...] = ()
    principal: Optional[str] = None
    request_id: Optional[str] = None
    ts: float = field(default_factory=time.time)
    worker: str = ""
    meta: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "seq": self.seq,
            "action": self.action,
            "ok": self.ok,
            "op_kinds": list(self.op_kinds),
            "principal": self.principal,
            "request_id": self.request_id,
            "ts": self.ts,
            "worker": self.worker,
            "meta": dict(self.meta),
        }

    @classmethod
    def from_dict(cls, d: dict) -> "IntentSyncMessage":
        return cls(
            seq=int(d.get("seq") or 0),
            action=str(d.get("action") or "?"),
            ok=bool(d.get("ok", True)),
            op_kinds=tuple(d.get("op_kinds") or ()),
            principal=d.get("principal"),
            request_id=d.get("request_id"),
            ts=float(d.get("ts") or time.time()),
            worker=str(d.get("worker") or ""),
            meta=dict(d.get("meta") or {}),
        )


class IntentSyncBus(Protocol):
    def publish(self, msg: IntentSyncMessage) -> int: ...
    def subscribe(self, handler: SyncHandler) -> None: ...
    def close(self) -> None: ...


class MemoryIntentSyncBus:
    """In-process fan-out (tests / single worker)."""

    def __init__(self) -> None:
        self._handlers: List[SyncHandler] = []
        self._lock = threading.Lock()
        self._seq = 0

    def next_seq(self) -> int:
        with self._lock:
            self._seq += 1
            return self._seq

    def publish(self, msg: IntentSyncMessage) -> int:
        with self._lock:
            hs = list(self._handlers)
        for h in hs:
            try:
                h(msg)
            except Exception:
                logger.exception("intent sync handler failed")
        return len(hs)

    def subscribe(self, handler: SyncHandler) -> None:
        with self._lock:
            self._handlers.append(handler)

    def close(self) -> None:
        with self._lock:
            self._handlers.clear()


class RedisIntentSyncBus:
    """
    Redis pub/sub intent sync.

    Channel: ``{prefix}events`` (default ``uidch:intent:sync:events``).
    Soft-fails publish when Redis is down (returns 0).
    """

    def __init__(
        self,
        redis_url: str | Any,
        *,
        prefix: str = "uidch:intent:sync:",
        soft_fail: bool = True,
        worker_id: str = "",
    ) -> None:
        from ux_channel.redis_extra.resilience import ResilientRedis

        self._rr = ResilientRedis(redis_url, soft_fail=soft_fail)
        self.prefix = prefix
        self.channel = f"{prefix}events"
        self.worker = worker_id or f"w-{threading.get_ident()}"
        self._handlers: List[SyncHandler] = []
        self._lock = threading.Lock()
        self._thread: Optional[threading.Thread] = None
        self._stop = threading.Event()
        self._pubsub = None
        self._seq_key = f"{prefix}seq"
        self._started = False

    def next_seq(self) -> int:
        def _incr(r: Any) -> int:
            return int(r.incr(self._seq_key))

        n = self._rr.execute(_incr, default=None)
        if n is None:
            # local fallback seq
            with self._lock:
                self._local_seq = getattr(self, "_local_seq", 0) + 1
                return int(self._local_seq)
        return int(n)

    def publish(self, msg: IntentSyncMessage) -> int:
        if not msg.worker:
            msg.worker = self.worker
        payload = _serde.dumps(msg.to_dict(), default=str)

        def _pub(r: Any) -> int:
            return int(r.publish(self.channel, payload) or 0)

        n = self._rr.execute(_pub, default=0)
        # local handlers always (same process)
        with self._lock:
            hs = list(self._handlers)
        for h in hs:
            try:
                h(msg)
            except Exception:
                logger.exception("local intent sync handler failed")
        return int(n) if n else len(hs)

    def subscribe(self, handler: SyncHandler) -> None:
        with self._lock:
            self._handlers.append(handler)
        self._ensure_listener()

    def _ensure_listener(self) -> None:
        if self._started:
            return
        self._started = True

        def loop() -> None:
            while not self._stop.is_set():
                try:
                    r = self._rr.client()
                    pub = r.pubsub(ignore_subscribe_messages=True)
                    pub.subscribe(self.channel)
                    self._pubsub = pub
                    while not self._stop.is_set():
                        try:
                            msg = pub.get_message(timeout=1.0)
                        except Exception:
                            break
                        if not msg or msg.get("type") != "message":
                            continue
                        data = msg.get("data")
                        if isinstance(data, bytes):
                            data = data.decode()
                        try:
                            parsed = IntentSyncMessage.from_dict(_serde.loads(data))
                        except Exception:
                            continue
                        # skip echo from same worker (already delivered locally)
                        if parsed.worker == self.worker:
                            continue
                        with self._lock:
                            hs = list(self._handlers)
                        for h in hs:
                            try:
                                h(parsed)
                            except Exception:
                                logger.exception("remote intent sync handler failed")
                except Exception as exc:
                    logger.warning("intent sync listener reconnect: %s", exc)
                    time.sleep(1.0)

        self._thread = threading.Thread(
            target=loop, name="uid-intent-sync", daemon=True
        )
        self._thread.start()

    def close(self) -> None:
        self._stop.set()
        try:
            if self._pubsub is not None:
                self._pubsub.close()
        except Exception:
            pass
        self._rr.close()
        with self._lock:
            self._handlers.clear()


def attach_intent_sync(
    channel: Any,
    bus: Any = None,
    *,
    redis_url: Optional[str] = None,
    on_sync: Optional[SyncHandler] = None,
    soft_fail: bool = True,
) -> Any:
    """
    After each Intent: publish a sync message on ``bus``.

    ::

        bus = attach_intent_sync(ch, redis_url=os.environ["REDIS_URL"])
        bus.subscribe(lambda m: print(m.action, m.ok))
    """
    if bus is None:
        if redis_url is not None:
            bus = RedisIntentSyncBus(redis_url, soft_fail=soft_fail)
        else:
            bus = MemoryIntentSyncBus()

    if on_sync is not None:
        bus.subscribe(on_sync)

    reg = channel.registry
    seq_fn = getattr(bus, "next_seq", None)

    def _after(intent: Any, result: Any) -> Any:
        try:
            if isinstance(intent, Intent):
                action = intent.action
                rid = intent.request_id
            else:
                action = str(intent.get("action", "?"))
                rid = intent.get("request_id")
            ops = tuple(
                str(o.get("op", "?"))
                for o in (getattr(result, "ops", None) or [])
                if isinstance(o, dict)
            )
            seq = int(seq_fn()) if callable(seq_fn) else 0
            msg = IntentSyncMessage(
                seq=seq,
                action=action,
                ok=bool(getattr(result, "ok", True)),
                op_kinds=ops,
                request_id=rid,
            )
            bus.publish(msg)
        except Exception:
            logger.exception("intent sync publish failed")
        return result

    reg.after(_after)
    channel.intent_sync = bus
    return bus
