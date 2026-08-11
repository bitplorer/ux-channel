"""Agent execution kernel — non-human tool callers (L4 plane).

Design
    Agents call the **same** action registry as humans, through a policy/budget
    door. No shadow Channel, no second database of actions.

Architecture
    L4 plane — import specific modules to avoid loading the full kernel.
    Application façade remains ``from ux_channel import agents``.

Implementation
    Preferred::

        from ux_channel.agent_runtime.peer import AgentPeer, dispatch_peer
        from ux_channel.agent_runtime import AgentRunner  # lazy
"""
from __future__ import annotations

from typing import Any

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
]

_LAZY = {
    "AgentPolicy": "ux_channel.agent_runtime.policy",
    "AgentSession": "ux_channel.agent_runtime.session",
    "AgentRunner": "ux_channel.agent_runtime.runner",
    "ToolCall": "ux_channel.agent_runtime.runner",
    "agent_tool": "ux_channel.agent_runtime.tools",
    "tools_from_registry": "ux_channel.agent_runtime.tools",
    "ToolMeta": "ux_channel.agent_runtime.tools",
    "AuditEvent": "ux_channel.agent_runtime.tool_audit",
    "LoggingAuditSink": "ux_channel.agent_runtime.tool_audit",
    "MemoryAuditSink": "ux_channel.agent_runtime.tool_audit",
    "MultiAuditSink": "ux_channel.agent_runtime.tool_audit",
    "AgentPeer": "ux_channel.agent_runtime.peer",
    "dispatch_peer": "ux_channel.agent_runtime.peer",
    "peer_intent": "ux_channel.agent_runtime.peer",
}


def __getattr__(name: str) -> Any:
    mod_name = _LAZY.get(name)
    if mod_name is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    import importlib

    mod = importlib.import_module(mod_name)
    val = getattr(mod, name)
    globals()[name] = val
    return val
