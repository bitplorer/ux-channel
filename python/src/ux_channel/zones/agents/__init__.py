"""Zone / package: **agents**

SUBPACKAGE: agent runners/tools.

Physical code: ``ux_channel.{pkg}`` (or existing subpackage).
"""
from __future__ import annotations
ZONE = 'agents'
DESCRIPTION = 'SUBPACKAGE: agent runners/tools.'
MEMBERS = {'audit': 'Agent audit log — every tool call is attributable in production.', 'policy': 'Agent / MCP policy — production guardrails for non-human callers.', 'runner': 'Safe agent/MCP tool runner — the only path agents should use to hit actions.', 'session': 'AgentSession — scoped identity + budgets for agent/MCP callers.', 'tools': 'Map Channel actions → agent/MCP tool definitions (JSON Schema-ish).'}
__all__ = ["ZONE", "DESCRIPTION", "MEMBERS", "help"]

def help() -> str:
    rows = "\n".join(f"  {k:28} {v}" for k, v in MEMBERS.items())
    return f"zone={ZONE}\n{DESCRIPTION}\n\n{rows}\n"
