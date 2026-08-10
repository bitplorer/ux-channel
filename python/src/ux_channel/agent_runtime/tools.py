"""
Map Channel actions → agent/MCP tool definitions (JSON Schema-ish).

Modular: does not depend on MCP transport; MCP adapter imports this.
"""

from __future__ import annotations

import inspect
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

from ux_channel.host.action_catalog import action_catalog
from ux_channel.host.registry import ActionRegistry


@dataclass
class ToolMeta:
    """Optional decorator metadata for agent-facing actions."""

    description: str = ""
    read_only: bool = False
    dangerous: bool = False
    tags: tuple[str, ...] = ()
    # JSON Schema fragment for args (optional override)
    input_schema: Optional[dict[str, Any]] = None


def agent_tool(
    description: str = "",
    *,
    read_only: bool = False,
    dangerous: bool = False,
    tags: tuple[str, ...] = (),
    input_schema: Optional[dict[str, Any]] = None,
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """
    Mark an action as agent/MCP-visible with richer metadata.

    Usage::

        @reg.action(\"Search.query\")
        @agent_tool(\"Search docs\", read_only=True, tags=(\"search\",))
        async def query(q: str):
            ...
    """

    def deco(fn: Callable[..., Any]) -> Callable[..., Any]:
        fn.__ux_tool__ = ToolMeta(  # type: ignore[attr-defined]
            description=description or (inspect.getdoc(fn) or fn.__name__),
            read_only=read_only,
            dangerous=dangerous,
            tags=tags,
            input_schema=input_schema,
        )
        return fn

    return deco


def _schema_from_signature(fn: Callable[..., Any]) -> dict[str, Any]:
    props: dict[str, Any] = {}
    required: list[str] = []
    sig = inspect.signature(fn)
    hints = getattr(fn, "__annotations__", {})
    for name, param in sig.parameters.items():
        if name == "ctx":
            continue
        if param.kind in (inspect.Parameter.VAR_POSITIONAL, inspect.Parameter.VAR_KEYWORD):
            continue
        ann = hints.get(name, param.annotation)
        typ = "string"
        if ann is int or ann == "int":
            typ = "integer"
        elif ann is float or ann == "float":
            typ = "number"
        elif ann is bool or ann == "bool":
            typ = "boolean"
        elif ann is dict or ann == "dict":
            typ = "object"
        elif ann is list or ann == "list":
            typ = "array"
        props[name] = {"type": typ, "description": name}
        if param.default is inspect.Parameter.empty:
            required.append(name)
    schema: dict[str, Any] = {"type": "object", "properties": props}
    if required:
        schema["required"] = required
    return schema


def tools_from_registry(
    registry: ActionRegistry,
    *,
    include: Optional[set[str]] = None,
    only_marked: bool = False,
) -> list[dict[str, Any]]:
    """
    Build MCP-compatible tool list entries.

    Each tool:
      { name, description, inputSchema, annotations: { readOnlyHint, ... } }
    """
    tools: list[dict[str, Any]] = []
    for entry in action_catalog(registry):
        name = entry["name"]
        if include is not None and name not in include:
            continue
        fn = registry.get(name)
        if fn is None:
            continue
        meta: Optional[ToolMeta] = getattr(fn, "__ux_tool__", None)
        if only_marked and meta is None:
            continue
        desc = (meta.description if meta else None) or entry.get("doc") or name
        schema = (meta.input_schema if meta and meta.input_schema else None) or _schema_from_signature(fn)
        tools.append(
            {
                "name": name,
                "description": desc,
                "inputSchema": schema,
                "annotations": {
                    "readOnlyHint": bool(meta.read_only) if meta else False,
                    "destructiveHint": bool(meta.dangerous) if meta else False,
                    "openWorldHint": False,
                    "uid": {
                        "async": entry["async"],
                        "tags": list(meta.tags) if meta else [],
                    },
                },
            }
        )
    return tools
