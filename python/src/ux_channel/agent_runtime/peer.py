"""Agent peer Intent path — part of the agent caller plane.

Application code prefers::

    from ux_channel import agents
    agents(ch).dispatch(action, args, peer=agents(ch).peer("bot-1"))

Power / tests::

    from ux_channel.agent_runtime import AgentPeer, dispatch_peer

Same Intent grammar, same caps, same registry as a human button.
Does **not** implement tools_for / situation / effects (that is AX
``devtools.agents_api``).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Optional

from ux_channel.protocol.types import Intent

__all__ = ["AgentPeer", "dispatch_peer", "peer_intent"]


@dataclass
class AgentPeer:
    """Identity for an agent acting as a control-plane peer."""

    id: str
    scopes: tuple[str, ...] = ()
    mint_caps: bool = True


def peer_intent(
    action: str,
    args: Optional[Mapping[str, Any]] = None,
    *,
    peer: Optional[AgentPeer] = None,
    request_id: Optional[str] = None,
) -> Intent:
    """Build an Intent for a peer (cap signing happens in ``dispatch_peer``)."""
    return Intent(
        action=action,
        args=dict(args or {}),
        request_id=request_id,
    )


def dispatch_peer(
    channel: Any,
    action: str,
    args: Optional[Mapping[str, Any]] = None,
    *,
    peer: Optional[AgentPeer] = None,
    principal: Any = None,
    async_: bool = False,
) -> Any:
    """
    Dispatch exactly like a button Intent — optional cap sign for agent.

    Cap is signed over **handler args only** (never mutate args after sign).
    Prefer ``agents(channel).dispatch(...)`` in application code.
    """
    reg = channel.registry
    args_d = dict(args or {})
    cap = None
    should_mint = peer is None or getattr(peer, "mint_caps", True)
    if should_mint and getattr(reg, "require_cap", False):
        mint_fn = getattr(reg, "mint", None)
        if callable(mint_fn):
            sub = getattr(peer, "id", None) if peer else None
            cap = mint_fn(action, args_d, sub=sub)
    intent = Intent(action=action, args=dict(args_d), cap=cap)
    if async_:
        return reg.async_dispatch(intent, principal=principal)
    return reg.dispatch(intent, principal=principal)
