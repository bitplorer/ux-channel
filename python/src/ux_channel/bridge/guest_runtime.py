"""Sealed guest runtime — islands may paint, not invent durable quantities.

* Enforces call budgets + refuse client quantity paths on events.
* Protocol allowlists come from ``bridge_protocol``."""


from __future__ import annotations

from ux_channel.protocol import serde as _serde

from dataclasses import dataclass, field
from typing import Any, Mapping, Optional, Sequence

from ux_channel.bridge.bridge_protocol import (
    BridgeFirewallError,
    SealedBridgeProtocol,
    get_sealed_registry,
)

__all__ = [
    "GuestBudget",
    "GuestMount",
    "GuestRuntimeError",
    "GuestRuntime",
    "event_to_intent_args",
]


class GuestRuntimeError(BridgeFirewallError):
    """Guest violated sealed policy."""


@dataclass(frozen=True)
class GuestBudget:
    """Resource budget for one island mount."""

    max_calls: int = 100
    max_events: int = 100
    max_payload_bytes: int = 64_000
    network: bool = False  # guest must not own channel network


@dataclass
class GuestMount:
    bridge_id: str
    package: str
    protocol: Optional[SealedBridgeProtocol] = None
    budget: GuestBudget = field(default_factory=GuestBudget)
    calls: int = 0
    events: int = 0

    def check_call(self, method: str, args: Any = None) -> list[Any]:
        self.calls += 1
        if self.calls > self.budget.max_calls:
            raise GuestRuntimeError(f"guest {self.bridge_id}: max_calls exceeded")
        raw = json_size(args)
        if raw > self.budget.max_payload_bytes:
            raise GuestRuntimeError(f"guest {self.bridge_id}: payload too large")
        proto = self.protocol or get_sealed_registry().get(self.package)
        if proto is None:
            raise GuestRuntimeError(
                f"guest {self.bridge_id}: no sealed protocol for {self.package!r}"
            )
        return proto.validate_call(method, args)

    def check_event(self, event: str, payload: Any = None) -> None:
        self.events += 1
        if self.events > self.budget.max_events:
            raise GuestRuntimeError(f"guest {self.bridge_id}: max_events exceeded")
        proto = self.protocol or get_sealed_registry().get(self.package)
        if proto is None:
            raise GuestRuntimeError(f"guest {self.bridge_id}: no sealed protocol")
        proto.allow_event(event)
        if json_size(payload) > self.budget.max_payload_bytes:
            raise GuestRuntimeError(f"guest {self.bridge_id}: event payload too large")


def json_size(obj: Any) -> int:
    """Byte size via process serde codec (best available backend)."""
    try:
        return _serde.size_of(obj)
    except Exception:
        return 0


def event_to_intent_args(
    event: str,
    payload: Mapping[str, Any] | None = None,
    *,
    allow_keys: Sequence[str] = (),
) -> dict[str, Any]:
    """
    Guest events → Intent args. Only allowlisted keys pass (never raw quantity authority).
    """
    from ux_channel.foundations.quantity import QuantityError, refuse_client_quantity

    out: dict[str, Any] = {"event": event}
    for k, v in dict(payload or {}).items():
        if allow_keys and k not in allow_keys:
            continue
        try:
            refuse_client_quantity(k, v)
        except QuantityError:
            continue  # drop quantity-like keys
        out[k] = v
    return out


class GuestRuntime:
    """Registry of active guest mounts for a channel process."""

    def __init__(self) -> None:
        self._mounts: dict[str, GuestMount] = {}

    def mount(
        self,
        bridge_id: str,
        package: str,
        *,
        budget: Optional[GuestBudget] = None,
    ) -> GuestMount:
        g = GuestMount(
            bridge_id=str(bridge_id),
            package=str(package),
            protocol=get_sealed_registry().get(package),
            budget=budget or GuestBudget(),
        )
        self._mounts[str(bridge_id)] = g
        return g

    def get(self, bridge_id: str) -> Optional[GuestMount]:
        return self._mounts.get(str(bridge_id))

    def call(self, bridge_id: str, method: str, args: Any = None) -> list[Any]:
        g = self._mounts.get(str(bridge_id))
        if g is None:
            raise GuestRuntimeError(f"guest {bridge_id!r} not mounted")
        return g.check_call(method, args)

    def event(self, bridge_id: str, event: str, payload: Any = None) -> None:
        g = self._mounts.get(str(bridge_id))
        if g is None:
            raise GuestRuntimeError(f"guest {bridge_id!r} not mounted")
        g.check_event(event, payload)
