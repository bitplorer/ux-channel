"""
Server push bus — server-initiated Results.

- In-memory (default): single process
- Redis pub/sub: multi-worker via ux_channel.redis_extra.RedisPushBus
"""

from __future__ import annotations

import asyncio
import gc
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
        # Unset means strict. A channel stamps "off" or "strict"; a bare bus does not.
        self.navigate_allowed_hosts: tuple[str, ...] = ()
        self._policy_bound = False
        self._owner: int | None = None

    def outbound_policy(self) -> str:
        """Policy for this bus.

        A missing value is strict (bare ``PushBus`` or a stream with no
        channel). A blank value is off, which is what a channel stamps when
        it has no policy. Any other value must be exactly ``off`` or ``strict``.
        """
        raw = getattr(self, "morph_html_policy", None)
        if raw is None:
            return "strict"
        if isinstance(raw, str) and raw.strip() == "":
            return "off"
        if raw not in ("off", "strict"):
            raise ValueError('morph_html_policy must be "off" or "strict"')
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


def _live_buses() -> list[PushBus]:
    """Distinct buses still held by a live owner.

    A registry and its Channel both attach the same bus, so they count once.
    Dead owners are dropped and do not keep a collected channel's bus alive.
    """
    found: list[PushBus] = []
    seen: set[int] = set()
    alive: list[weakref.ReferenceType[Any]] = []
    for ref in list(_owners):
        owner = ref()
        if owner is None:
            continue
        alive.append(ref)
        bus = getattr(owner, "push_bus", None)
        if not isinstance(bus, PushBus) or id(bus) in seen:
            continue
        seen.add(id(bus))
        found.append(bus)
    _owners[:] = alive
    return found


def get_push_bus(channel: Any = None) -> PushBus:
    """Process bus when at most one channel is booted.

    With two or more live channels this raises. Pass ``channel`` to take
    that channel's bus. A bare bus with no channel is unchanged.
    """
    global _bus
    if channel is not None:
        bus = getattr(channel, "push_bus", None)
        if not isinstance(bus, PushBus):
            reg = getattr(channel, "registry", None)
            reg_bus = getattr(reg, "push_bus", None) if reg is not None else None
            bus = reg_bus if isinstance(reg_bus, PushBus) else None
        if not isinstance(bus, PushBus):
            raise RuntimeError("channel has no push bus")
        return bus
    live = _live_buses()
    if len(live) > 1:
        # Finished tests can leave a registry in a cycle until collection.
        # Channels the caller still holds stay, and still raise.
        gc.collect()
        live = _live_buses()
    if len(live) > 1:
        raise RuntimeError(
            "more than one channel is booted; pass the channel to get_push_bus(channel)"
        )
    if len(live) == 1:
        return live[0]
    # A collected channel must not leave its bus as the process singleton.
    if _bus is not None and getattr(_bus, "_owner", None) is not None:
        _bus = None
    if _bus is None:
        _bus = PushBus()
    return _bus


def stream_filter_args(
    registry: Any, config: Any = None
) -> tuple[str, tuple[str, ...]]:
    """Policy and navigate hosts the action stream must use for this channel.

    The bus stamp wins. A channel with no bus and no config is off.
    """
    bus = getattr(registry, "push_bus", None)
    if isinstance(bus, PushBus):
        hosts = tuple(getattr(bus, "navigate_allowed_hosts", ()) or ())
        return bus.outbound_policy(), hosts
    cfg = getattr(registry, "config", None) or config
    if cfg is None:
        return "off", ()
    raw = getattr(cfg, "morph_html_policy", None)
    if raw is None or (isinstance(raw, str) and str(raw).strip() == ""):
        policy = "off"
    elif raw not in ("off", "strict"):
        raise ValueError('morph_html_policy must be "off" or "strict"')
    else:
        policy = str(raw)
    hosts = tuple(getattr(cfg, "navigate_allowed_hosts", ()) or ())
    return policy, hosts


def registry_push_bus(registry: Any) -> PushBus:
    """The bus mounted for this registry. No process-bus fallback."""
    bus = getattr(registry, "push_bus", None)
    if not isinstance(bus, PushBus):
        raise RuntimeError("channel has no push bus")
    return bus


def ensure_registry_push_bus(registry: Any) -> PushBus:
    """Attach a bus when ``mount_channel`` did not go through the factory.

    The first mount shares the process bus, which is main's one-channel
    behaviour. A later mount gets its own bus and does not borrow another
    channel's.
    """
    existing = getattr(registry, "push_bus", None)
    if isinstance(existing, PushBus):
        return existing
    if _live_buses():
        bus = PushBus()
    else:
        bus = get_push_bus()
    # Attaching makes this a channel bus. No policy yet means off, not strict.
    if not getattr(bus, "_policy_bound", False) and not hasattr(bus, "morph_html_policy"):
        bus.morph_html_policy = "off"
    attach_push_bus(registry, bus)
    return bus


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
