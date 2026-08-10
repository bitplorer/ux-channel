"""Agent execution kernel — production-safe non-human callers.

This is **not** a second Channel. It is the only path agents / MCP tools
should use to hit the same action registry humans reach via Intent + caps.

Boundary
--------
* Human UI path: ``Channel`` + Intent + caps (untouched).
* Agent/tool path: ``AgentRunner.call_tool`` → policy → session budget → Intent.
* Product façade: ``from ux_channel import agents`` → ``agents(ch)`` (devtools).
* MCP transport: ``ux_channel.mcp`` builds on ``AgentRunner``.
* Island guests: ``bridge.guest_runtime`` (separate trust class — not this package).

See root ``MENTAL_MODEL.md`` § Caller planes.
"""
from __future__ import annotations

# MANUAL_PUBLIC_API

from ux_channel.agent_runtime.tool_audit import (
    AuditEvent,
    LoggingAuditSink,
    MemoryAuditSink,
    MultiAuditSink,
)
from ux_channel.agent_runtime.policy import AgentPolicy
from ux_channel.agent_runtime.runner import AgentRunner, ToolCall
from ux_channel.agent_runtime.session import AgentSession
from ux_channel.agent_runtime.peer import AgentPeer, dispatch_peer, peer_intent
from ux_channel.agent_runtime.tools import ToolMeta, agent_tool, tools_from_registry

PACKAGE = "agent_runtime"
__all__ = [
    "PACKAGE",
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
