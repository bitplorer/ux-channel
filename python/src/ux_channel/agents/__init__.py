"""
Agents module — production-safe AI agent integration for ux-channel.

Modular boundary: UI Intent path stays untouched; agents enter via AgentRunner.

Also: this package is **callable** so ``from ux_channel import agents`` keeps
working after ``from ux_channel.agents import AgentRunner`` (submodule import
would otherwise shadow the ``agents(ch)`` façade function with a bare module).

Peer Intent path lives in ``ux_channel.agent_peer`` (not this package) to avoid
import cycles with ``agents_api``.
"""

from __future__ import annotations

import sys
from types import ModuleType
from typing import Any

from ux_channel.agents.audit import (
    AuditEvent,
    LoggingAuditSink,
    MemoryAuditSink,
    MultiAuditSink,
)
from ux_channel.agents.policy import AgentPolicy
from ux_channel.agents.runner import AgentRunner, ToolCall
from ux_channel.agents.session import AgentSession
from ux_channel.agents.tools import agent_tool, tools_from_registry, ToolMeta


class _AgentsPackage(ModuleType):
    """Module that is also the product ``agents(ch)`` façade when imported as attribute."""

    def __call__(self, channel: Any, **kwargs: Any) -> Any:
        from ux_channel.ops_dx.agents_api import agents as _facade

        return _facade(channel, **kwargs)


_mod = sys.modules[__name__]
_mod.__class__ = _AgentsPackage  # type: ignore[misc]

try:
    import ux_channel as _parent
    from ux_channel.ops_dx.agents_api import agents as _facade_fn

    if getattr(_parent, "agents", None) is _mod:
        pass
    setattr(_parent, "agents", _facade_fn)
except Exception:
    pass

from ux_channel.ops_dx.agents_api import Agents, EffectReport, agents, attach_agents  # noqa: E402
from ux_channel.ops_dx.agent_peer import AgentPeer, dispatch_peer, peer_intent  # noqa: E402

__all__ = [
    "AgentPolicy",
    "AgentSession",
    "AgentRunner",
    "ToolCall",
    "agent_tool",
    "tools_from_registry",
    "ToolMeta",
    "AuditEvent",
    "LoggingAuditSink",
    "MemoryAuditSink",
    "MultiAuditSink",
    "AgentPeer",
    "dispatch_peer",
    "peer_intent",
    "agents",
    "Agents",
    "attach_agents",
    "EffectReport",
]
