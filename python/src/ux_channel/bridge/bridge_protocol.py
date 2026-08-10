"""Sealed bridge protocols — guest islands may only use declared methods/events.

* Fail closed: unknown methods/events raise ``BridgeFirewallError``.
* Complements ``guest_runtime`` budgets and channel caps."""


from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping, MutableMapping, Optional, Sequence

from ux_channel.bridge.bridge_contract import BridgeContract, MethodSpec, ValidationError

__all__ = [
    "BridgeFirewallError",
    "SealedBridgeProtocol",
    "SealedRegistry",
    "get_sealed_registry",
    "reset_sealed_registry",
]


class BridgeFirewallError(ValidationError):
    """Method or event not allowed by sealed protocol."""


@dataclass
class SealedBridgeProtocol:
    """
    Guest contract: methods in, events out — nothing else.

    ``strict=True`` (default): unknown method/event raises.
    """

    name: str
    methods: dict[str, MethodSpec] = field(default_factory=dict)
    events: frozenset[str] = field(default_factory=frozenset)
    version: str = "1"
    strict: bool = True
    # optional package id for docs only
    package: Optional[str] = None

    def allow_call(self, method: str) -> None:
        if method not in self.methods:
            if self.strict:
                raise BridgeFirewallError(
                    f"bridge {self.name!r}: method {method!r} not in sealed protocol"
                )
        return None

    def allow_event(self, event: str) -> None:
        if event not in self.events:
            if self.strict:
                raise BridgeFirewallError(
                    f"bridge {self.name!r}: event {event!r} not in sealed protocol"
                )

    def validate_call(self, method: str, args: Any = None) -> list[Any]:
        self.allow_call(method)
        spec = self.methods[method]
        return spec.validate_args(args)

    def to_contract(self) -> BridgeContract:
        return BridgeContract(
            package=self.package or self.name,
            methods=dict(self.methods),
            version=self.version,
            events=tuple(sorted(self.events)),
        )

    @classmethod
    def from_contract(
        cls,
        contract: BridgeContract,
        *,
        events: Iterable[str] = (),
        strict: bool = True,
        package: Optional[str] = None,
    ) -> "SealedBridgeProtocol":
        ev = events if events else (contract.events or ())
        return cls(
            name=package or contract.package,
            methods=dict(contract.methods),
            events=frozenset(str(e) for e in ev),
            version=str(getattr(contract, "version", "1") or "1"),
            strict=strict,
            package=package or contract.package,
        )


class SealedRegistry:
    """name → SealedBridgeProtocol."""

    def __init__(self) -> None:
        self._p: dict[str, SealedBridgeProtocol] = {}

    def register(self, protocol: SealedBridgeProtocol) -> SealedBridgeProtocol:
        self._p[protocol.name] = protocol
        return protocol

    def get(self, name: str) -> Optional[SealedBridgeProtocol]:
        return self._p.get(name)

    def require(self, name: str) -> SealedBridgeProtocol:
        p = self.get(name)
        if p is None:
            raise BridgeFirewallError(f"no sealed protocol {name!r}")
        return p

    def validate_call(self, name: str, method: str, args: Any = None) -> list[Any]:
        return self.require(name).validate_call(method, args)

    def names(self) -> list[str]:
        return sorted(self._p)


_SEALED = SealedRegistry()


def get_sealed_registry() -> SealedRegistry:
    """Process-wide sealed protocol registry (used by ch.bridge.call)."""
    return _SEALED


def reset_sealed_registry() -> SealedRegistry:
    """Tests only — clear sealed protocols."""
    global _SEALED
    _SEALED = SealedRegistry()
    return _SEALED
