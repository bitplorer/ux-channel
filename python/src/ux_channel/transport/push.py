"""
Server push bus — server-initiated Results.

- In-memory (default): single process
- Redis pub/sub: multi-worker via ux_channel.redis_extra.RedisPushBus
"""

from __future__ import annotations

import asyncio
import threading
import weakref
from collections import defaultdict
from typing import Any, DefaultDict, Optional, Protocol, Set

from ux_channel.protocol.types import Result
from ux_channel.security.security import filter_outbound_ops


class PushBackend(Protocol):
    def publish(self, topic: str, payload: dict) -> int: ...
    def subscribe_local(self, topic: str, queue: asyncio.Queue) -> None: ...
    def unsubscribe_local(self, topic: str, queue: asyncio.Queue) -> None: ...


class MemoryPushBackend:
    def __init__(self) -> None:
        self._subs: DefaultDict[str, Set[asyncio.Queue]] = defaultdict(set)
        self._lock = threading.Lock()

    def publish(self, topic: str, payload: dict) -> int:
        """
        Fan-out to local SSE/WS queues.

        On ``QueueFull``: drop the oldest item then retry once so live UIs
        prefer *fresh* morphs over silent total loss (SSE refresh reliability).
        """
        with self._lock:
            qs = list(self._subs.get(topic, ()))
        n = 0
        for q in qs:
            try:
                q.put_nowait(payload)
                n += 1
            except asyncio.QueueFull:
                try:
                    q.get_nowait()  # drop oldest
                except Exception:
                    pass
                try:
                    q.put_nowait(payload)
                    n += 1
                except asyncio.QueueFull:
                    # still full — skip this subscriber
                    pass
        return n

    def subscribe_local(self, topic: str, queue: asyncio.Queue) -> None:
        with self._lock:
            self._subs[topic].add(queue)

    def unsubscribe_local(self, topic: str, queue: asyncio.Queue) -> None:
        with self._lock:
            self._subs[topic].discard(queue)
            if not self._subs[topic]:
                del self._subs[topic]

    def topics(self) -> list[str]:
        with self._lock:
            return sorted(self._subs.keys())


class PushBus:
    def __init__(self, backend: Optional[PushBackend] = None) -> None:
        self.backend: PushBackend = backend or MemoryPushBackend()
        # Stamped from this channel's config. Unset means strict (fail closed).
        self.morph_html_policy = "off"
        self.navigate_allowed_hosts: tuple[str, ...] = ()
        self._policy_bound = False
        self._owner: int | None = None

    def outbound_policy(self) -> str:
        """Policy for this bus. A missing value is strict."""
        raw = getattr(self, "morph_html_policy", None)
        if raw is None or str(raw).strip() == "":
            return "strict"
        return str(raw)

    def subscribe(self, topic: str, queue: asyncio.Queue) -> None:
        self.backend.subscribe_local(topic, queue)

    def unsubscribe(self, topic: str, queue: asyncio.Queue) -> None:
        self.backend.unsubscribe_local(topic, queue)

    def publish(self, topic: str, result: Result | dict) -> int:
        body = result.to_dict() if isinstance(result, Result) else dict(result)
        ops = body.get("ops")
        if isinstance(ops, list):
            body["ops"] = filter_outbound_ops(
                ops,
                policy=self.outbound_policy(),
                allowed_hosts=tuple(getattr(self, "navigate_allowed_hosts", ()) or ()),
            )
        return self.backend.publish(topic, body)

    def topics(self) -> list[str]:
        b = self.backend
        if hasattr(b, "topics"):
            return b.topics()  # type: ignore[attr-defined]
        return []


_bus: Optional[PushBus] = None
_owners: list[weakref.ReferenceType[Any]] = []


def get_push_bus() -> PushBus:
    global _bus
    if _bus is None:
        _bus = PushBus()
    return _bus


def attach_push_bus(owner: Any, bus: PushBus) -> None:
    """Remember ``owner`` so a later ``set_push_bus`` can keep its policy."""
    owner.push_bus = bus
    _owners.append(weakref.ref(owner))


def set_push_bus(bus: PushBus) -> None:
    """Install ``bus``. An unbound replacement keeps the previous policy.

    A bus a channel already stamped (``_policy_bound``) is left as that
    channel configured it, so a second boot does not rewrite the first.
    """
    global _bus
    prev = _bus
    inherited = False
    if prev is not None and bus is not prev and not getattr(bus, "_policy_bound", False):
        if hasattr(prev, "morph_html_policy"):
            bus.morph_html_policy = prev.morph_html_policy
        elif hasattr(bus, "morph_html_policy"):
            del bus.morph_html_policy
        bus.navigate_allowed_hosts = tuple(
            getattr(prev, "navigate_allowed_hosts", ()) or ()
        )
        bus._policy_bound = bool(getattr(prev, "_policy_bound", False))
        bus._owner = getattr(prev, "_owner", None)
        inherited = True
    _bus = bus
    if not inherited or prev is None:
        return
    for ref in list(_owners):
        owner = ref()
        if owner is not None and getattr(owner, "push_bus", None) is prev:
            owner.push_bus = bus
