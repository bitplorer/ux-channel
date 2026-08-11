"""MCP adapter package — tools, effects, verticals, sessions (L4 plane).

Design
    Non-human tool door into the **same** action registry. MCP is a plane, not
    a second Channel or shadow action table.

Architecture
    L4 — sessions/verticals/resources hang off the adapter; confirm paths need
    signed secrets (fail-closed). Not on root exports.

Implementation
    Preferred::

        from ux_channel.mcp import McpToolAdapter, effects_from_result
"""
from ux_channel.mcp.adapter import McpToolAdapter
from ux_channel.mcp.effects import effects_from_result
from ux_channel.mcp.verticals import (
    VerticalPack,
    filter_tools_by_verticals,
    list_verticals,
    register_builtin_verticals,
    register_vertical,
)
from ux_channel.mcp.annotations import enrich_tools, classify_tool
from ux_channel.mcp.subscribe import subscribe_info, publish_effects_invalidation

__all__ = [
    "McpToolAdapter",
    "effects_from_result",
    "VerticalPack",
    "register_vertical",
    "register_builtin_verticals",
    "list_verticals",
    "filter_tools_by_verticals",
    "enrich_tools",
    "classify_tool",
    "subscribe_info",
    "publish_effects_invalidation",
]
