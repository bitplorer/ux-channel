"""Zone / package: **mcp**

SUBPACKAGE: MCP tool plane.

Physical code: ``ux_channel.{pkg}`` (or existing subpackage).
"""
from __future__ import annotations
ZONE = 'mcp'
DESCRIPTION = 'SUBPACKAGE: MCP tool plane.'
MEMBERS = {'adapter': 'MCP-shaped adapter (Model Context Protocol tool surface).', 'annotations': 'Enrich MCP tool descriptors with vertical / outbox / I/O annotations.', 'asgi_routes': 'HTTP routes for agent/MCP tool access (modular mount).', 'confirm': 'Signed confirmation tokens for MCP / agent high-stakes tools.', 'effects': 'Normalize Result → agent-facing effects envelope (MCP _meta.effects).', 'resources': 'MCP resources — read-only context (situation, region, claim, verticals).', 'sessions': 'Claim-bound MCP sessions.', 'subscribe': 'MCP resource subscribe — invalidate/notify over the channel push bus (SSE).', 'verticals': 'Vertical packs — installable MCP product slices.'}
__all__ = ["ZONE", "DESCRIPTION", "MEMBERS", "help"]

def help() -> str:
    rows = "\n".join(f"  {k:28} {v}" for k, v in MEMBERS.items())
    return f"zone={ZONE}\n{DESCRIPTION}\n\n{rows}\n"
