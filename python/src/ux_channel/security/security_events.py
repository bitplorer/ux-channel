"""
Structured security event stream — Wireshark-like Developer tooling for auth doors.

WHY
---
Production needs a single place to see: cap fails, origin denies, ticket
expiry, rate limits, WS floods. Apps bind a sink (log, metrics, SIEM).

USAGE
-----
::

    from ux_channel.security.security_events import get_security_bus, SecurityEvent
    get_security_bus().emit("cap_fail", action="Orders.place", reason="bad cap")
"""

from __future__ import annotations

import logging
import threading
import time
from collections import deque
from dataclasses import asdict, dataclass, field
from typing import Any, Callable, Deque, List, Optional

logger = logging.getLogger("ux_channel.security.security")


@dataclass
class SecurityEvent:
    kind: str
    ts: float = field(default_factory=time.time)
    reason: str = ""
    action: str = ""
    topic: str = ""
    principal: str = ""
    client: str = ""
    meta: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        d = asdict(self)
        return d


Sink = Callable[[SecurityEvent], None]


class SecurityEventBus:
    """Ring buffer + fan-out sinks for security events."""

    def __init__(self, *, retain: int = 500) -> None:
        self._lock = threading.Lock()
        self._events: Deque[SecurityEvent] = deque(maxlen=max(10, retain))
        self._sinks: List[Sink] = []
        self.retain = retain

    def add_sink(self, fn: Sink) -> None:
        self._sinks.append(fn)

    def emit(
        self,
        kind: str,
        *,
        reason: str = "",
        action: str = "",
        topic: str = "",
        principal: str = "",
        client: str = "",
        **meta: Any,
    ) -> SecurityEvent:
        ev = SecurityEvent(
            kind=str(kind),
            reason=str(reason or ""),
            action=str(action or ""),
            topic=str(topic or ""),
            principal=str(principal or ""),
            client=str(client or ""),
            meta=dict(meta) if meta else {},
        )
        with self._lock:
            self._events.append(ev)
            sinks = list(self._sinks)
        logger.info(
            "security kind=%s reason=%s action=%s topic=%s",
            ev.kind,
            ev.reason,
            ev.action,
            ev.topic,
        )
        for s in sinks:
            try:
                s(ev)
            except Exception:  # noqa: BLE001
                logger.exception("security sink failed")
        return ev

    def recent(self, n: int = 50, *, kind: Optional[str] = None) -> list[dict]:
        with self._lock:
            items = list(self._events)
        if kind:
            items = [e for e in items if e.kind == kind]
        return [e.to_dict() for e in items[-n:]]

    def clear(self) -> None:
        with self._lock:
            self._events.clear()


_bus: Optional[SecurityEventBus] = None
_bus_lock = threading.Lock()


def get_security_bus() -> SecurityEventBus:
    global _bus
    with _bus_lock:
        if _bus is None:
            _bus = SecurityEventBus()
        return _bus


def set_security_bus(bus: SecurityEventBus) -> None:
    global _bus
    with _bus_lock:
        _bus = bus


def emit_security(kind: str, **kwargs: Any) -> SecurityEvent:
    return get_security_bus().emit(kind, **kwargs)
