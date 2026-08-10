"""MCP adapter package — tools, effects, verticals, sessions, resources, subscribe."""

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
    "publish_effects_invalidation"]
