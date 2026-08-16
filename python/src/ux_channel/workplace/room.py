"""Workplace room façade — claim · gate · AX · I/O (package-private module).

Public: ``from ux_channel.workplace import Workplace, workplace``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Optional, Sequence

from ux_channel.devtools.agents_api import Agents, agents as agents_facade
from ux_channel.foundations.io_channel import (
    IoAdapter,
    IoAuditLog,
    IoChannelError,
    IoGate,
    IoInvocation,
    IoRoomClaim,
    attach_io_audit,
    attach_io_gate,
    claim_from_mapping,
    get_io_audit,
    get_io_gate,
    run_checked,
)
from ux_channel.foundations.quantity import Quantity
from ux_channel.protocol.types import Result
from ux_channel.workplace.ticket import (
    claim_from_workplace_ticket,
    revoke_workplace_ticket,
    sign_workplace_ticket,
)

class WorkplaceError(IoChannelError):
    """Workplace policy or lifecycle error."""


def _action_allowed_by_claim(action: str, claim: IoRoomClaim) -> bool:
    """
    True if claim may intent this action name.

    Rules (stable, conservative):
    * empty claim scopes → allow all (open desk; app should set scopes in prod)
    * action name or its dotted prefix matches a claim scope
    * scope ``*`` allows all
    """
    if not claim.alive():
        return False
    if not claim.scopes or "*" in claim.scopes:
        return True
    a = str(action)
    if claim.allows_scope(a):
        return True
    head = a.split(".", 1)[0]
    if claim.allows_scope(head):
        return True
    for sc in claim.scopes:
        if a == sc or a.startswith(sc + ".") or a.startswith(sc + "_"):
            return True
    return False


@dataclass
class Workplace:
    """
    One policy-shaped room bound to a Channel.

    Surfaces
    --------
    * ``claim`` — mesh membership (not ambient trust)
    * ``gate`` — sealed I/O protocols
    * ``io_audit`` — I/O policy tape
    * ``dispatch`` / ``tools_for`` / ``situation`` — claim-aware AX
    * ``run_io`` / ``check_event`` — adapter path
    * ``control`` — claim-aware UI cap mint
    * ``membership_ticket`` — token for revoke when built from ticket_token
    """

    ch: Any
    claim: IoRoomClaim
    gate: IoGate = field(default_factory=IoGate)
    io_audit: Optional[IoAuditLog] = None
    _adapters: dict[str, IoAdapter] = field(default_factory=dict)
    _action_allow: Optional[frozenset[str]] = None
    _action_deny: frozenset[str] = field(default_factory=frozenset)
    _facts: dict[str, Any] = field(default_factory=dict)
    membership_ticket: Optional[str] = None

    def rebind(
        self,
        claim: Optional[IoRoomClaim] = None,
        *,
        ticket: Optional[Mapping[str, Any]] = None,
        ticket_token: Optional[str] = None,
        room: Optional[str] = None,
    ) -> "Workplace":
        """Replace membership claim (ticket refresh / room hop)."""
        if ticket_token is not None:
            claim = claim_from_workplace_ticket(
                self.ch.config, ticket_token, room=room
            )
            self.membership_ticket = ticket_token
        if ticket is not None and claim is None:
            claim = claim_from_mapping(ticket)
        if claim is None:
            raise WorkplaceError("rebind requires claim=, ticket=, or ticket_token=")
        self.claim = claim
        return self

    def narrow(self, scopes: Sequence[str]) -> "Workplace":
        """Attenuate claim scopes only (fail if widen)."""
        self.claim = self.claim.narrow(frozenset(str(s) for s in scopes))
        return self

    def require_alive(self) -> None:
        if not self.claim.alive():
            raise WorkplaceError(
                f"workplace room {self.claim.room!r} claim expired — mesh ≠ trust"
            )

    def allow(self, *adapters: IoAdapter) -> "Workplace":
        """Register adapter protocols on the gate (fail-closed methods)."""
        for ad in adapters:
            proto = ad.describe()
            self.gate.register(proto)
            self._adapters[proto.name] = ad
        return self

    def adapter(self, protocol_name: str) -> IoAdapter:
        if protocol_name not in self._adapters:
            raise WorkplaceError(f"no adapter registered for {protocol_name!r}")
        return self._adapters[protocol_name]

    def allow_actions(
        self,
        names: Optional[Sequence[str]] = None,
        *,
        deny: Sequence[str] = (),
    ) -> "Workplace":
        """Optional explicit action allow/deny lists (intersected with claim)."""
        if names is not None:
            self._action_allow = frozenset(str(n) for n in names)
        self._action_deny = frozenset(str(n) for n in deny)
        return self

    def allows_action(self, action: str) -> bool:
        self.require_alive()
        a = str(action)
        if a in self._action_deny:
            return False
        if self._action_allow is not None and a not in self._action_allow:
            return False
        return _action_allowed_by_claim(a, self.claim)

    def ensure_action(self, action: str) -> None:
        if not self.allows_action(action):
            raise WorkplaceError(
                f"action {action!r} not allowed under claim scopes "
                f"{sorted(self.claim.scopes)} room={self.claim.room!r}"
            )

    def run_io(
        self,
        protocol: str,
        method: str,
        args: Sequence[Any] = (),
        *,
        quantity: Optional[Quantity] = None,
        claim: Optional[IoRoomClaim] = None,
    ) -> Any:
        """``run_checked`` under this workplace's claim (or override)."""
        self.require_alive()
        ad = self.adapter(protocol)
        c = claim or self.claim
        return run_checked(
            self.gate,
            ad,
            method,
            args,
            claim=c,
            quantity=quantity,
            audit=self.io_audit,
            protocol_name=protocol,
        )

    def check_io(
        self,
        protocol: str,
        method: str,
        args: Sequence[Any] = (),
        *,
        quantity: Optional[Quantity] = None,
        claim: Optional[IoRoomClaim] = None,
    ) -> IoInvocation:
        """Policy check only (no adapter call)."""
        self.require_alive()
        return self.gate.check(
            protocol,
            method,
            args,
            claim=claim or self.claim,
            quantity=quantity,
        )

    def check_event(
        self,
        protocol: str,
        event: str,
        payload: Mapping[str, Any] | None = None,
        *,
        method_for_keys: Optional[str] = None,
        claim: Optional[IoRoomClaim] = None,
    ) -> dict[str, Any]:
        """Sealed event → Intent args (quantity keys stripped)."""
        self.require_alive()
        return self.gate.check_event(
            protocol,
            event,
            payload,
            claim=claim or self.claim,
            method_for_keys=method_for_keys,
        )

    def _agents(self) -> Agents:
        return agents_facade(self.ch)

    def peer(self, id: Optional[str] = None, *, scopes: Sequence[str] = ()):
        """Agent peer attributed to this room; scopes default to claim scopes."""
        sc = tuple(scopes) if scopes else tuple(sorted(self.claim.scopes))
        return self._agents().peer(id or self.claim.peer_id, scopes=sc)

    def tools_for(self, **kwargs: Any) -> list[dict[str, Any]]:
        """Registry tools filtered to actions this claim may invoke."""
        self.require_alive()
        tools = self._agents().tools_for(**kwargs)
        return [t for t in tools if self.allows_action(str(t.get("name") or ""))]

    def situation(
        self,
        facts: Optional[Mapping[str, Any]] = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """AX situation plus workplace membership metadata."""
        self.require_alive()
        merged = dict(self._facts)
        if facts:
            merged.update(dict(facts))
        sit = self._agents().situation(facts=merged, **kwargs)
        sit["workplace"] = self.snapshot()
        sit["tools"] = self.tools_for()
        return sit

    def put_facts(self, **facts: Any) -> "Workplace":
        self._facts.update(facts)
        return self

    def dispatch(
        self,
        action: str,
        args: Optional[Mapping[str, Any]] = None,
        *,
        peer: Any = None,
        **kwargs: Any,
    ) -> Result:
        """Same Intent path as buttons/agents; refuse if claim denies action."""
        self.ensure_action(action)
        p = peer if peer is not None else self.peer()
        return self._agents().dispatch(action, args or {}, peer=p, **kwargs)

    async def async_dispatch(
        self,
        action: str,
        args: Optional[Mapping[str, Any]] = None,
        *,
        peer: Any = None,
        **kwargs: Any,
    ) -> Result:
        self.ensure_action(action)
        p = peer if peer is not None else self.peer()
        return await self._agents().async_dispatch(
            action, args or {}, peer=p, **kwargs
        )

    dispatch_async = async_dispatch

    def control(
        self,
        action: Any,
        *,
        trust: Optional[Mapping[str, Any]] = None,
        target: Optional[str] = None,
        cap: Optional[str] = None,
        mint_cap: bool = True,
        sub: Optional[str] = None,
        once: bool = False,
        scopes: Optional[Sequence[str]] = None,
        extra: Optional[Mapping[str, str]] = None,
        enforce: bool = True,
        **trust_fields: Any,
    ) -> Any:
        """
        Mint control attrs under this room claim.

        * ``enforce=True`` (default): refuse actions the claim cannot run.
        * Cap ``scopes`` default to claim scopes (attenuated).
        * ``sub`` defaults to ``claim.peer_id``.
        """
        action_name, _ = self.ch._resolve_action_target(action, target)
        if enforce:
            self.ensure_action(action_name)
        sc = list(scopes) if scopes is not None else list(sorted(self.claim.scopes))
        if self.claim.scopes and "*" not in self.claim.scopes:
            sc = [s for s in sc if self.claim.allows_scope(s) or s in self.claim.scopes]
        return self.ch.control(
            action,
            trust=trust,
            target=target,
            cap=cap,
            mint_cap=mint_cap,
            sub=sub if sub is not None else self.claim.peer_id,
            once=once,
            scopes=sc or None,
            extra=extra,
            **trust_fields,
        )

    def mint_ticket(
        self,
        *,
        scopes: Optional[Sequence[str]] = None,
        trust: Optional[Mapping[str, str]] = None,
        max_age: Optional[int] = None,
        sub: Optional[str] = None,
    ) -> str:
        """Re-mint a workplace ticket for this claim (refresh / handoff)."""
        sc = scopes if scopes is not None else sorted(self.claim.scopes)
        if self.claim.scopes and "*" not in self.claim.scopes:
            sc = [s for s in sc if s in self.claim.scopes]
        tok = sign_workplace_ticket(
            self.ch.config,
            self.claim.room,
            sub=sub if sub is not None else self.claim.peer_id,
            scopes=sc,
            trust=trust if trust is not None else dict(self.claim.trust),
            max_age=max_age,
        )
        self.membership_ticket = tok
        return tok

    def revoke_membership(self, *, ttl_s: float | None = None) -> None:
        """Revoke ``membership_ticket`` if known (logout this room)."""
        if not self.membership_ticket:
            raise WorkplaceError(
                "no membership_ticket on workplace — use revoke_mesh_membership(mem) "
                "or workplace(..., ticket_token=...)"
            )
        age = ttl_s
        if age is None and self.claim.expires_at is not None:
            import time

            age = max(60.0, float(self.claim.expires_at) - time.time())
        revoke_workplace_ticket(self.membership_ticket, ttl_s=age)

    def snapshot(self) -> dict[str, Any]:
        return {
            "room": self.claim.room,
            "peer_id": self.claim.peer_id,
            "scopes": sorted(self.claim.scopes),
            "expires_at": self.claim.expires_at,
            "alive": self.claim.alive(),
            "adapters": sorted(self._adapters.keys()),
            "protocols": sorted(self.gate.protocols.keys()),
            "action_allow": sorted(self._action_allow) if self._action_allow else None,
            "action_deny": sorted(self._action_deny),
            "has_membership_ticket": bool(self.membership_ticket),
        }

    def export_io_audit(self) -> list[dict[str, Any]]:
        if self.io_audit is None:
            return []
        return self.io_audit.export()


def workplace(
    channel: Any,
    *,
    claim: Optional[IoRoomClaim] = None,
    ticket: Optional[Mapping[str, Any]] = None,
    ticket_token: Optional[str] = None,
    room: Optional[str] = None,
    gate: Optional[IoGate] = None,
    io_audit: Optional[IoAuditLog] = None,
    attach: bool = True,
) -> Workplace:
    """
    Build a Workplace for ``channel``.

    Provide one of:
    * ``claim=`` — ready ``IoRoomClaim``
    * ``ticket=`` — mapping → ``claim_from_mapping``
    * ``ticket_token=`` — signed workplace ticket (``sign_workplace_ticket``)

    When ``attach=True`` (default), stores as ``channel._workplace`` and
    reuses/attaches process-level IoGate / IoAuditLog.
    """
    saved_token = ticket_token
    if claim is None and ticket_token is not None:
        claim = claim_from_workplace_ticket(
            channel.config, ticket_token, room=room
        )
    if claim is None and ticket is not None:
        claim = claim_from_mapping(ticket)
    if claim is None:
        raise WorkplaceError(
            "workplace() requires claim=, ticket=, or ticket_token="
        )

    g = gate or get_io_gate(channel) or attach_io_gate(channel)
    if gate is not None and attach:
        attach_io_gate(channel, gate)

    audit = io_audit
    if audit is None:
        audit = get_io_audit(channel)
    if audit is None:
        audit = attach_io_audit(channel)

    wp = Workplace(
        ch=channel,
        claim=claim,
        gate=g,
        io_audit=audit,
        membership_ticket=saved_token,
    )
    if attach:
        channel._workplace = wp
    return wp




def attach_workplace(channel: Any, wp: Workplace) -> Workplace:
    """Attach workplace + its IoGate (and audit) to ``channel``."""
    channel._workplace = wp
    attach_io_gate(channel, wp.gate)
    if wp.io_audit is not None:
        attach_io_audit(channel, wp.io_audit)
    return wp


def get_workplace(channel: Any) -> Optional[Workplace]:
    """Return the Workplace attached to ``channel``, if any."""
    w = getattr(channel, "_workplace", None)
    return w if isinstance(w, Workplace) else None
