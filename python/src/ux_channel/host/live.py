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

Multi-worker live updates: publish a Result on the **push bus**
(``get_push_bus().publish``) with Redis backend; each worker applies or
forwards as configured.

See: docs/SSE.md, docs/WEBSOCKET.md, docs/COURSE.md.
"""
from __future__ import annotations

import threading
import time
from collections import defaultdict
from typing import Any, DefaultDict, Dict, List, Optional, Sequence, Set


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
        from ux_channel.transport.push import get_push_bus
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
        return get_push_bus().publish(topic, body)

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


def touch_presence(topic: str, client_id: str, *, ttl_s: float = 60) -> int:
    """Record a live subscriber; returns approximate count for topic."""
    now = time.time()
    with _global_presence_lock:
        bucket = _global_presence[topic]
        bucket[client_id] = now + max(5.0, float(ttl_s))
        dead = [k for k, exp in bucket.items() if exp < now]
        for k in dead:
            del bucket[k]
        return len(bucket)


def presence_count(topic: str) -> int:
    now = time.time()
    with _global_presence_lock:
        bucket = _global_presence.get(topic, {})
        return sum(1 for exp in bucket.values() if exp >= now)


def presence_snapshot() -> dict[str, int]:
    now = time.time()
    with _global_presence_lock:
        return {
            t: sum(1 for exp in b.values() if exp >= now)
            for t, b in _global_presence.items()
        }


def attach_live(channel: Any) -> LivePlane:
    plane = LivePlane(channel)
    channel.live = plane
    return plane
