"""I/O channel — authorize and record I/O intents; never own device buses.
CONSTITUTION (long-term stable)
uxchannel is a **capability-shaped I/O channel** for multi-actor workplaces
(UI · agents · edge adapters), including **mesh membership**. It is **not**
a device driver, soft PLC, or protocol stack (GPIO, OPC-UA, ROS, Matter, …).
    Mesh is how envelopes travel.
    Channel is how authority…"""

from __future__ import annotations

from ux_channel.protocol import serde as _serde

from dataclasses import dataclass, field
from decimal import Decimal
from enum import Enum
from typing import (
    Any,
    Callable,
    Mapping,
    Optional,
    Protocol,
    Sequence,
    Union,
    runtime_checkable,
)

from ux_channel.bridge.bridge_contract import MethodSpec
from ux_channel.bridge.bridge_protocol import BridgeFirewallError, SealedBridgeProtocol
from ux_channel.bridge.guest_runtime import event_to_intent_args
from ux_channel.foundations.quantity import Quantity, QuantityBudget, QuantityError

__all__ = [
    "IO_LAWS",
    "IO_CONSTITUTION",
    "IoKind",
    "IoChannelError",
    "IoMethodSpec",
    "IoProtocol",
    "IoRoomClaim",
    "IoGate",
    "IoAdapter",
    "IoInvocation",
    "IoAuditRecord",
    "IoAuditLog",
    "attach_io_gate",
    "get_io_gate",
    "attach_io_audit",
    "get_io_audit",
    "command_budget_allows",
    "reading_to_quantity",
    "event_args_for_intent",
    "claim_from_mapping",
    "claim_from_ticket_claims",
    "protocol_from_mapping",
    "load_protocol_json",
    "run_checked",
]


# Constitution (importable; tests and docs pin these)

IO_CONSTITUTION = (
    "uxchannel is the capability-shaped I/O channel for multi-actor mesh "
    "workplaces; drivers and protocols live in adapters."
)

IO_LAWS: tuple[str, ...] = (
    "no_effect_without_intent",
    "scopes_attenuate_only",
    "chrome_is_not_quantity",
    "adapters_fail_closed",
    "commands_discrete_loops_local",
    "audit_physical_acts",
    "ax_same_registry",
    "mesh_is_not_trust",
)


class IoKind(str, Enum):
    """Effect class — decides how strictly the channel treats a method."""

    COMMAND = "command"
    READING = "reading"
    STREAM = "stream"


class IoChannelError(ValueError):
    """I/O channel policy violation (not a device error)."""


@dataclass(frozen=True)
class IoMethodSpec:
    """
    One sealed adapter method.

    ``scopes`` — action/domain scopes required on the room claim / cap.
    ``unit`` / ``max_magnitude`` — optional QuantityBudget for COMMAND methods.
    ``allow_event_keys`` — when this method is triggered from an adapter event,
    only these payload keys may become Intent args (quantity-ish keys dropped).
    """

    name: str
    kind: IoKind = IoKind.COMMAND
    scopes: frozenset[str] = field(default_factory=frozenset)
    unit: str = ""
    max_magnitude: Optional[Union[Decimal, int, float, str]] = None
    allow_event_keys: tuple[str, ...] = ()
    description: str = ""

    def budget(self) -> Optional[QuantityBudget]:
        if self.max_magnitude is None and not self.unit:
            return None
        max_m: Optional[Decimal] = None
        if self.max_magnitude is not None:
            max_m = Decimal(str(self.max_magnitude))
        return QuantityBudget(max_magnitude=max_m, unit=self.unit or "")


@dataclass(frozen=True)
class IoProtocol:
    """
    Sealed I/O contract for one adapter package (fail closed).

    Interop: ``to_sealed_bridge()`` for guest/bridge planes that already
    understand ``SealedBridgeProtocol``.
    """

    name: str
    methods: Mapping[str, IoMethodSpec] = field(default_factory=dict)
    events: frozenset[str] = field(default_factory=frozenset)
    version: str = "1"
    strict: bool = True

    def get(self, method: str) -> IoMethodSpec:
        if method not in self.methods:
            if self.strict:
                raise IoChannelError(
                    f"io {self.name!r}: method {method!r} not in sealed protocol"
                )
            raise IoChannelError(f"io {self.name!r}: unknown method {method!r}")
        return self.methods[method]

    def allow_event(self, event: str) -> None:
        if event not in self.events:
            if self.strict:
                raise IoChannelError(
                    f"io {self.name!r}: event {event!r} not in sealed protocol"
                )

    def to_sealed_bridge(self) -> SealedBridgeProtocol:
        """Project to existing sealed guest contract (methods + events only)."""
        return SealedBridgeProtocol(
            name=self.name,
            methods={
                n: MethodSpec(n)
                for n, m in self.methods.items()
                if m.kind != IoKind.STREAM
            },
            events=self.events,
            version=self.version,
            strict=self.strict,
            package=self.name,
        )


@dataclass(frozen=True)
class IoRoomClaim:
    """
    Mesh membership claim — **not** ambient trust.

    ``room`` — mesh group id (WebRTC room, workplace cell, …).
    ``scopes`` — attenuated domains this peer may intent (subset only).
    ``peer_id`` — stable peer / adapter identity for audit.
    ``expires_at`` — optional unix seconds; expired claim cannot command.
    """

    room: str
    scopes: frozenset[str]
    peer_id: str
    expires_at: Optional[float] = None
    trust: Mapping[str, str] = field(default_factory=dict)

    def alive(self, *, now: Optional[float] = None) -> bool:
        if self.expires_at is None:
            return True
        import time

        t = time.time() if now is None else now
        return t <= float(self.expires_at)

    def allows_scope(self, scope: str) -> bool:
        if not self.alive():
            return False
        s = str(scope)
        if s in self.scopes:
            return True
        # prefix: scope "pay" allows action "pay.order" style names
        return any(s == sc or s.startswith(sc + ".") for sc in self.scopes)

    def allows_method(self, method: IoMethodSpec) -> bool:
        if not self.alive():
            return False
        if not method.scopes:
            return True
        return all(self.allows_scope(sc) for sc in method.scopes)

    def narrow(self, scopes: frozenset[str]) -> "IoRoomClaim":
        """Attenuate only — child scopes must be ⊆ parent."""
        child = frozenset(scopes)
        if not child.issubset(self.scopes):
            raise IoChannelError(
                f"room claim cannot widen scopes: {sorted(child - self.scopes)}"
            )
        return IoRoomClaim(
            room=self.room,
            scopes=child,
            peer_id=self.peer_id,
            expires_at=self.expires_at,
            trust=dict(self.trust),
        )


@dataclass(frozen=True)
class IoInvocation:
    """Checked request ready for an adapter (still not a driver call)."""

    protocol: str
    method: str
    kind: IoKind
    args: tuple[Any, ...]
    claim: IoRoomClaim
    quantity: Optional[Quantity] = None


def command_budget_allows(
    method: IoMethodSpec,
    quantity: Optional[Quantity],
) -> bool:
    """True if COMMAND method's optional QuantityBudget accepts quantity."""
    if method.kind != IoKind.COMMAND:
        return True
    budget = method.budget()
    if budget is None:
        return True
    if quantity is None:
        # budget exists but no quantity supplied — refuse (fail closed)
        return False
    return budget.allows(quantity)


def reading_to_quantity(
    magnitude: Any,
    unit: str,
    *,
    source: str,
    revision: Union[str, int] = 0,
    principal: Optional[str] = None,
) -> Quantity:
    """
    Stamp a READING as store/adapter-grounded Quantity.

    Adapters call this after a physical read — channel never invents source.
    """
    return Quantity.from_store(
        magnitude,
        unit,
        source=source,
        revision=revision,
        principal=principal,
    )


def event_args_for_intent(
    event: str,
    payload: Mapping[str, Any] | None = None,
    *,
    allow_keys: Sequence[str] = (),
) -> dict[str, Any]:
    """
    Adapter/guest event → Intent args (allowlist + drop quantity-ish keys).

    Same law as ``guest_runtime.event_to_intent_args`` — one mutation door.
    """
    return event_to_intent_args(event, payload, allow_keys=allow_keys)


@dataclass
class IoGate:
    """
    Policy gate: room claim + sealed protocol + optional Quantity budget.

    Does **not** perform I/O. Call ``check`` then your adapter ``call``.
    """

    protocols: dict[str, IoProtocol] = field(default_factory=dict)

    def register(self, protocol: IoProtocol) -> "IoGate":
        self.protocols[protocol.name] = protocol
        return self

    def check(
        self,
        protocol_name: str,
        method: str,
        args: Sequence[Any] = (),
        *,
        claim: IoRoomClaim,
        quantity: Optional[Quantity] = None,
    ) -> IoInvocation:
        if not claim.alive():
            raise IoChannelError("room claim expired — mesh membership is not trust")
        proto = self.protocols.get(protocol_name)
        if proto is None:
            raise IoChannelError(f"unknown io protocol {protocol_name!r}")
        spec = proto.get(method)
        if spec.kind == IoKind.STREAM:
            raise IoChannelError(
                f"{method!r} is STREAM — use media/side plane, not Intent/I/O gate"
            )
        if not claim.allows_method(spec):
            raise IoChannelError(
                f"claim scopes {sorted(claim.scopes)} cannot invoke "
                f"{method!r} requiring {sorted(spec.scopes)}"
            )
        if spec.kind == IoKind.COMMAND and not command_budget_allows(spec, quantity):
            raise IoChannelError(
                f"command {method!r} rejected by QuantityBudget "
                f"(unit={spec.unit!r}, max={spec.max_magnitude!r})"
            )
        return IoInvocation(
            protocol=protocol_name,
            method=method,
            kind=spec.kind,
            args=tuple(args),
            claim=claim,
            quantity=quantity,
        )

    def check_event(
        self,
        protocol_name: str,
        event: str,
        payload: Mapping[str, Any] | None = None,
        *,
        claim: IoRoomClaim,
        method_for_keys: Optional[str] = None,
    ) -> dict[str, Any]:
        """Validate sealed event + build Intent args (quantity keys stripped)."""
        if not claim.alive():
            raise IoChannelError("room claim expired")
        proto = self.protocols.get(protocol_name)
        if proto is None:
            raise IoChannelError(f"unknown io protocol {protocol_name!r}")
        proto.allow_event(event)
        allow: Sequence[str] = ()
        if method_for_keys and method_for_keys in proto.methods:
            allow = proto.methods[method_for_keys].allow_event_keys
        return event_args_for_intent(event, payload, allow_keys=allow)


@runtime_checkable
class IoAdapter(Protocol):
    """
    Host-owned adapter port — **you** implement drivers here.

    Channel code must not import OS/hardware stacks; only this port.
    """

    def describe(self) -> IoProtocol:
        """Sealed methods/events this adapter exposes."""
        ...

    def call(
        self,
        method: str,
        args: Sequence[Any],
        *,
        claim: IoRoomClaim,
        quantity: Optional[Quantity] = None,
    ) -> Any:
        """Perform I/O only after ``IoGate.check`` (caller's duty)."""
        ...


def attach_io_gate(channel: Any, gate: Optional[IoGate] = None) -> IoGate:
    """Attach an ``IoGate`` to a Channel process (optional power helper)."""
    existing = getattr(channel, "_io_gate", None)
    if isinstance(existing, IoGate) and gate is None:
        return existing
    g = gate or IoGate()
    channel._io_gate = g
    return g


def get_io_gate(channel: Any) -> Optional[IoGate]:
    """Return the IoGate attached to ``channel``, if any."""
    g = getattr(channel, "_io_gate", None)
    return g if isinstance(g, IoGate) else None


# Mesh ticket → room claim (B1)


def claim_from_mapping(
    data: Mapping[str, Any],
    *,
    default_room: str = "",
    default_peer: str = "anonymous",
) -> IoRoomClaim:
    """
    Build ``IoRoomClaim`` from a plain mapping (JWT claims, ticket dict, session).

    Recognized keys (first hit wins for aliases)::

        room | room_id
        peer_id | sub | peer
        scopes | scope  (list/tuple/str comma-separated)
        exp | expires_at  (unix seconds)
        trust  (dict of str→str ids only)
    """
    room = str(data.get("room") or data.get("room_id") or default_room or "")
    peer = str(
        data.get("peer_id") or data.get("sub") or data.get("peer") or default_peer
    )
    raw_scopes = data.get("scopes", data.get("scope", ()))
    if isinstance(raw_scopes, str):
        scopes = frozenset(s.strip() for s in raw_scopes.split(",") if s.strip())
    else:
        scopes = frozenset(str(s) for s in (raw_scopes or ()))
    exp = data.get("expires_at", data.get("exp"))
    expires_at: Optional[float]
    if exp is None or exp == "":
        expires_at = None
    else:
        expires_at = float(exp)
    trust_raw = data.get("trust") or {}
    trust = {str(k): str(v) for k, v in dict(trust_raw).items()}
    if not room:
        raise IoChannelError("claim mapping requires room / room_id")
    return IoRoomClaim(
        room=room,
        scopes=scopes,
        peer_id=peer,
        expires_at=expires_at,
        trust=trust,
    )


def claim_from_ticket_claims(
    claims: Mapping[str, Any],
    *,
    default_room: str = "",
    default_peer: str = "anonymous",
) -> IoRoomClaim:
    """Alias of ``claim_from_mapping`` for WebRTC / push ticket payloads."""
    return claim_from_mapping(
        claims, default_room=default_room, default_peer=default_peer
    )


# Protocol JSON (C3)


def protocol_from_mapping(data: Mapping[str, Any]) -> IoProtocol:
    """Load ``IoProtocol`` from a JSON-serializable dict (contract file)."""
    methods: dict[str, IoMethodSpec] = {}
    for name, raw in dict(data.get("methods") or {}).items():
        if isinstance(raw, IoMethodSpec):
            methods[str(name)] = raw
            continue
        r = dict(raw or {})
        kind = r.get("kind", "command")
        if isinstance(kind, IoKind):
            k = kind
        else:
            k = IoKind(str(kind))
        scopes = r.get("scopes") or ()
        if isinstance(scopes, str):
            sc = frozenset(s.strip() for s in scopes.split(",") if s.strip())
        else:
            sc = frozenset(str(s) for s in scopes)
        aek = r.get("allow_event_keys") or ()
        methods[str(name)] = IoMethodSpec(
            name=str(name),
            kind=k,
            scopes=sc,
            unit=str(r.get("unit") or ""),
            max_magnitude=r.get("max_magnitude"),
            allow_event_keys=tuple(str(x) for x in aek),
            description=str(r.get("description") or ""),
        )
    events = data.get("events") or ()
    if isinstance(events, str):
        ev = frozenset(s.strip() for s in events.split(",") if s.strip())
    else:
        ev = frozenset(str(e) for e in events)
    return IoProtocol(
        name=str(data.get("name") or "unnamed"),
        methods=methods,
        events=ev,
        version=str(data.get("version") or "1"),
        strict=bool(data.get("strict", True)),
    )


def load_protocol_json(path: Union[str, Any]) -> IoProtocol:
    """Load protocol contract from a JSON file path."""
    import json
    from pathlib import Path as _Path

    p = _Path(path)
    return protocol_from_mapping(_serde.loads(p.read_text(encoding="utf-8")))


# Audit I/O invocations (D1)


@dataclass(frozen=True)
class IoAuditRecord:
    """One checked I/O attempt (policy layer — not device telemetry)."""

    protocol: str
    method: str
    kind: str
    room: str
    peer_id: str
    ok: bool
    error: Optional[str] = None
    quantity: Optional[dict[str, Any]] = None
    meta: Mapping[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "protocol": self.protocol,
            "method": self.method,
            "kind": self.kind,
            "room": self.room,
            "peer_id": self.peer_id,
            "ok": self.ok,
            "error": self.error,
            "quantity": self.quantity,
            "meta": dict(self.meta),
        }


class IoAuditLog:
    """In-process I/O audit tape (pair with attach_audit for Intent trail)."""

    def __init__(self, *, maxlen: int = 2000) -> None:
        self._rows: list[IoAuditRecord] = []
        self.maxlen = int(maxlen)

    def record(self, row: IoAuditRecord) -> None:
        self._rows.append(row)
        if len(self._rows) > self.maxlen:
            self._rows = self._rows[-self.maxlen :]

    def since(self, n: int = 0) -> list[IoAuditRecord]:
        if n <= 0:
            return list(self._rows)
        return list(self._rows[n:])

    def export(self) -> list[dict[str, Any]]:
        return [r.to_dict() for r in self._rows]


def attach_io_audit(channel: Any, log: Optional[IoAuditLog] = None) -> IoAuditLog:
    """Attach (or reuse) an IoAuditLog on ``channel``."""
    existing = getattr(channel, "_io_audit", None)
    if isinstance(existing, IoAuditLog) and log is None:
        return existing
    lg = log or IoAuditLog()
    channel._io_audit = lg
    return lg


def get_io_audit(channel: Any) -> Optional[IoAuditLog]:
    """Return the IoAuditLog attached to ``channel``, if any."""
    lg = getattr(channel, "_io_audit", None)
    return lg if isinstance(lg, IoAuditLog) else None


# Checked run: gate + adapter + audit (B2 / D1)


def run_checked(
    gate: IoGate,
    adapter: IoAdapter,
    method: str,
    args: Sequence[Any] = (),
    *,
    claim: IoRoomClaim,
    quantity: Optional[Quantity] = None,
    audit: Optional[IoAuditLog] = None,
    protocol_name: Optional[str] = None,
) -> Any:
    """
    Fail-closed path: describe → check → call → audit.

    ``protocol_name`` defaults to ``adapter.describe().name``.
    """
    proto = adapter.describe()
    pname = protocol_name or proto.name
    if pname not in gate.protocols:
        gate.register(proto)
    try:
        inv = gate.check(pname, method, args, claim=claim, quantity=quantity)
        result = adapter.call(
            inv.method, inv.args, claim=inv.claim, quantity=inv.quantity
        )
        if audit is not None:
            qdict = quantity.to_dict() if quantity is not None else None
            audit.record(
                IoAuditRecord(
                    protocol=pname,
                    method=method,
                    kind=inv.kind.value,
                    room=claim.room,
                    peer_id=claim.peer_id,
                    ok=True,
                    quantity=qdict,
                )
            )
        return result
    except Exception as exc:
        if audit is not None:
            kind = "command"
            try:
                kind = proto.get(method).kind.value
            except Exception:
                pass
            audit.record(
                IoAuditRecord(
                    protocol=pname,
                    method=method,
                    kind=kind,
                    room=claim.room,
                    peer_id=claim.peer_id,
                    ok=False,
                    error=f"{type(exc).__name__}: {exc}",
                    quantity=quantity.to_dict() if quantity is not None else None,
                )
            )
        raise
