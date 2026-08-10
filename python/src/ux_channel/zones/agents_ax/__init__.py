"""Zone: **agents_ax**

Agent Experience + MCP — **tools/situation, not core UI regions**.

This package does **not** move implementations. It is a **navigation + re-export hub**
so you never have to guess intent from a flat 100-file directory listing.

Canonical implementations still live at ``ux_channel.<module>`` (stable import paths).
Prefer day-1: ``from ux_channel.day1 import ...``.

Members
-------
* ``agents_api`` — agents(ch) AX façade
* ``agent_peer`` — Internal agent Intent path
* ``agents`` — SUBPACKAGE: agent runners/tools
* ``mcp`` — SUBPACKAGE: MCP tool plane
"""
from __future__ import annotations

ZONE = "agents_ax"
DESCRIPTION = 'Agent Experience + MCP — **tools/situation, not core UI regions**.'

MEMBERS: dict[str, str] = {
    'agents_api': 'agents(ch) AX façade',
    'agent_peer': 'Internal agent Intent path',
    'agents': 'SUBPACKAGE: agent runners/tools',
    'mcp': 'SUBPACKAGE: MCP tool plane',
}

__all__ = ["ZONE", "DESCRIPTION", "MEMBERS", "help"]

def help() -> str:
    """Human summary of this zone."""
    rows = "\n".join(f"  {k:24} {v}" for k, v in MEMBERS.items())
    return f"zone={ZONE}\n{DESCRIPTION}\n\n{rows}\n"

