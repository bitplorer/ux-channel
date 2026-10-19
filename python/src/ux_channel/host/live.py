"""
Live plane — in-process topic → region bindings.

First principles
----------------
``ch.live.bind("rates", ticker_region)`` records which regions to refresh
when something **publishes** to a topic **inside this process**.

It is **not**:

- Redis pub/sub
- SSE/WebSocket subscribe (clients use push topics + tickets)
- A guarantee across Gunicorn workers

Multi-worker live updates: publish a Result on this channel's push bus
with a Redis backend; each worker applies or forwards as configured.

See: docs/SSE.md, docs/WEBSOCKET.md, docs/COURSE.md.
"""
from __future__ import annotations

import threading
import time
from collections import defaultdict
from typing import Any, DefaultDict, Dict, List, Optional


class LivePlane:
    def __init__(self, channel: Any) -> None:
        self.ch = channel
        self._lock = threading.Lock()
        self._bindings: Dict[str, List[str]] = {}
        self._presence: DefaultDict[str, Dict[str, float]] = defaultdict(dict)
        self._seq: Dict[str, int] = {}

    def bind(self, topic: str, *uids: Any) -> "LivePlane":
        """Declare regions that refresh when ``topic`` is published."""
        resolved: list[str] = []
        for u in uids:
            if u is None:
                continue
            if hasattr(u, "uid") and not isinstance(u, str):
                resolved.append(str(u.uid))
            else:
                resolved.append(str(u))
        with self._lock:
            cur = list(self._bindings.get(topic, []))
            for r in resolved:
                if r not in cur:
                    cur.append(r)
            self._bindings[topic] = cur
        return self

    def unbind(self, topic: str, *uids: str) -> None:
        with self._lock:
            if not uids:
                self._bindings.pop(topic, None)
                return
            cur = [u for u in self._bindings.get(topic, []) if u not in uids]
            if cur:
                self._bindings[topic] = cur
            else:
                self._bindings.pop(topic, None)

    def bindings(self) -> dict[str, list[str]]:
        with self._lock:
            return {k: list(v) for k, v in self._bindings.items()}

    def regions_for(self, topic: str) -> list[str]:
        with self._lock:
            return list(self._bindings.get(topic, ()))

    def next_seq(self, topic: str) -> int:
        with self._lock:
            n = int(self._seq.get(topic, 0)) + 1
            self._seq[topic] = n
            return n

    def publish(
        self,
        topic: str,
        *extra_uids: Any,
        result: Any = None,
        notice: Optional[str] = None,
    ) -> int:
        """
        Publish a Result to ``topic``.

        If ``result`` is None, builds ``ch.refresh(*bound, *extra)``.
        """
        from ux_channel.protocol.types import Result

        uids: list[str] = list(self.regions_for(topic))
        for u in extra_uids:
            if u is None:
                continue
            s = str(u.uid) if hasattr(u, "uid") and not isinstance(u, str) else str(u)
            if s not in uids:
                uids.append(s)
        if result is None:
            if not uids:
                # empty success — still useful as heartbeat
                result = Result.success()
            else:
                result = self.ch.refresh(*uids)
                if notice and hasattr(result, "ops"):
                    # append toast if builder available
                    try:
                        from ux_channel.protocol.ops import toast

                        result = Result(
                            ok=getattr(result, "ok", True),
                            ops=list(result.ops) + [toast(notice)],
                            error=getattr(result, "error", None),
                            meta=dict(getattr(result, "meta", None) or {}),
                            v=getattr(result, "v", "1"),
                        )
                    except Exception:
                        pass
        if not isinstance(result, Result) and not isinstance(result, dict):
            raise TypeError("live.publish expects Result, dict, or region uids")
        body = result.to_dict() if isinstance(result, Result) else dict(result)
        meta = dict(body.get("meta") or {})
        meta["seq"] = self.next_seq(topic)
        meta["topic"] = topic
        body["meta"] = meta
        reg = getattr(self.ch, "registry", None)
        bus = getattr(reg, "push_bus", None) if reg is not None else None
        if bus is None:
            bus = getattr(self.ch, "push_bus", None)
        if bus is None:
            raise RuntimeError("channel has no push bus")
        return bus.publish(topic, body)

    # --- presence (Wave 2 / 5) ---------------------------------------------

    def presence_touch(self, topic: str, client_id: str, *, ttl_s: float = 60) -> int:
        """Record a subscriber heartbeat; returns approx live count."""
        return touch_presence(topic, client_id, ttl_s=ttl_s)

    def presence_count(self, topic: str) -> int:
        return presence_count(topic)

    def presence_snapshot(self) -> dict[str, int]:
        return presence_snapshot()


# Process-wide presence (ASGI has registry, not always Channel)
_global_presence: DefaultDict[str, Dict[str, float]] = defaultdict(dict)
_global_presence_lock = threading.Lock()


def _presence_ttl(ttl_s: float) -> float:
    """Honor the caller TTL. Zero or negative expires on the next read."""
    try:
        return max(0.0, float(ttl_s))
    except (TypeError, ValueError):
        return 60.0


def _purge_expired(bucket: Dict[str, float], now: float) -> None:
    dead = [k for k, exp in bucket.items() if exp <= now]
    for k in dead:
        del bucket[k]


def touch_presence(topic: str, client_id: str, *, ttl_s: float = 60) -> int:
    """Record a live subscriber; returns approximate count for topic."""
    now = time.time()
    ttl = _presence_ttl(ttl_s)
    with _global_presence_lock:
        bucket = _global_presence[topic]
        _purge_expired(bucket, now)
        if ttl > 0:
            bucket[client_id] = now + ttl
        else:
            bucket.pop(client_id, None)
        if not bucket:
            _global_presence.pop(topic, None)
            return 0
        return len(bucket)


def presence_count(topic: str) -> int:
    now = time.time()
    with _global_presence_lock:
        bucket = _global_presence.get(topic)
        if not bucket:
            return 0
        _purge_expired(bucket, now)
        if not bucket:
            _global_presence.pop(topic, None)
            return 0
        return len(bucket)


def presence_snapshot() -> dict[str, int]:
    now = time.time()
    with _global_presence_lock:
        for topic in list(_global_presence):
            _purge_expired(_global_presence[topic], now)
            if not _global_presence[topic]:
                _global_presence.pop(topic, None)
        return {t: len(b) for t, b in _global_presence.items()}


def attach_live(channel: Any) -> LivePlane:
    plane = LivePlane(channel)
    channel.live = plane
    return plane
