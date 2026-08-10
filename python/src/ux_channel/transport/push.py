"""
Server push bus — server-initiated Results.

- In-memory (default): single process
- Redis pub/sub: multi-worker via ux_channel.redis_extra.RedisPushBus
"""

from __future__ import annotations

import asyncio
import json
import threading
from collections import defaultdict
from typing import Any, DefaultDict, Optional, Protocol, Set

from ux_channel.protocol.types import Result


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

    def subscribe(self, topic: str, queue: asyncio.Queue) -> None:
        self.backend.subscribe_local(topic, queue)

    def unsubscribe(self, topic: str, queue: asyncio.Queue) -> None:
        self.backend.unsubscribe_local(topic, queue)

    def publish(self, topic: str, result: Result | dict) -> int:
        body = result.to_dict() if isinstance(result, Result) else dict(result)
        return self.backend.publish(topic, body)

    def topics(self) -> list[str]:
        b = self.backend
        if hasattr(b, "topics"):
            return b.topics()  # type: ignore[attr-defined]
        return []


_bus: Optional[PushBus] = None


def get_push_bus() -> PushBus:
    global _bus
    if _bus is None:
        _bus = PushBus()
    return _bus


def set_push_bus(bus: PushBus) -> None:
    global _bus
    _bus = bus
