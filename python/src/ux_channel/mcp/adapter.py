"""
MCP-shaped adapter (Model Context Protocol tool surface).

Does not require the official MCP SDK. Speaks common tool shapes:

  - tools/list  → { tools: [...] }
  - tools/call  → { content, isError, structuredContent, _meta.effects }
  - resources/* → uid:// situation · region · claim · verticals

Also exposes a simple JSON-RPC 2.0 handler for embedding.
"""

from __future__ import annotations

from typing import Any, Mapping, Optional, Sequence

from ux_channel.agent_runtime.runner import AgentRunner, ToolCall
from ux_channel.mcp.effects import effects_from_result
from ux_channel.mcp.verticals import filter_tools_by_verticals
from ux_channel.mcp.annotations import enrich_tools
from ux_channel.mcp.subscribe import publish_effects_invalidation, subscribe_info
from ux_channel.protocol.types import Result


class McpToolAdapter:
    """
    Bind an AgentRunner to MCP tool list/call semantics.

    Optional vertical filter and resource context for claim-bound sessions.
    """

    def __init__(
        self,
        runner: AgentRunner,
        *,
        only_marked: bool = True,
        verticals: Sequence[str] = (),
        resource_regions: Sequence[str] = (),
        room: str = "",
        scopes: Sequence[str] = (),
        sub: str = "",
        channel: Any = None,
    ):
        self.runner = runner
        self.only_marked = only_marked
        self.verticals = tuple(verticals or ())
        self.resource_regions = tuple(resource_regions or ())
        self.room = room or ""
        self.scopes = tuple(scopes or ())
        self.sub = sub or ""
        self.channel = channel

    def list_tools(self) -> dict[str, Any]:
        tools = self.runner.list_tools(only_marked=self.only_marked)
        tools = filter_tools_by_verticals(tools, self.verticals)
        tools = enrich_tools(tools, verticals=self.verticals)
        return {"tools": tools}

    async def call_tool(
        self,
        name: str,
        arguments: Optional[Mapping[str, Any]] = None,
        *,
        confirmation: Optional[str] = None,
        dry_run: Optional[bool] = None,
        call_id: Optional[str] = None,
    ) -> dict[str, Any]:
        result = await self.runner.call_tool_async(
            ToolCall(
                name=name,
                arguments=dict(arguments or {}),
                confirmation=confirmation,
                dry_run=dry_run,
                call_id=call_id,
            )
        )
        return self._format_result(result)

    def call_tool_sync(
        self, name: str, arguments: Optional[Mapping[str, Any]] = None, **kw
    ) -> dict[str, Any]:
        result = self.runner.call_tool(
            ToolCall(name=name, arguments=dict(arguments or {}), **kw)
        )
        return self._format_result(result)

    def list_resources(self) -> dict[str, Any]:
        from ux_channel.mcp.resources import list_resources

        return {
            "resources": list_resources(
                room=self.room,
                region_uids=self.resource_regions,
                verticals=self.verticals,
                has_claim=bool(self.room or self.scopes),
            )
        }

    def read_resource(self, uri: str) -> dict[str, Any]:
        from ux_channel.mcp.resources import read_resource

        ch = self.channel
        situation_fn = None
        if ch is not None:
            try:
                from ux_channel import agents

                ag = agents(ch)

                def situation_fn(facts):  # type: ignore[misc]
                    return ag.situation(facts=facts)

            except Exception:
                situation_fn = None

        return read_resource(
            uri,
            channel=ch,
            room=self.room,
            scopes=self.scopes,
            sub=self.sub,
            verticals=self.verticals,
            region_uids=self.resource_regions,
            situation_fn=situation_fn,
        )

    def _format_result(self, result: Result) -> dict[str, Any]:
        summary = "ok" if result.ok else f"error: {result.error.code if result.error else 'unknown'}"
        if result.error:
            summary = f"{result.error.code}: {result.error.message}"
        elif result.meta.get("dry_run"):
            summary = f"dry_run would_call={result.meta.get('would_call')}"
        else:
            ops = ",".join(o.get("op", "?") for o in result.ops[:8])
            summary = f"ok ops=[{ops}]"

        effects = effects_from_result(result)
        # confirmation_required is a protocol branch, not transport failure
        is_error = not result.ok and not (
            result.error and result.error.code == "confirmation_required"
        )

        body: dict[str, Any] = {
            "content": [{"type": "text", "text": summary}],
            "isError": is_error,
            "structuredContent": result.to_dict(),
            "_meta": {
                "v": "1",
                "session_id": self.runner.session.session_id,
                "agent_id": self.runner.session.agent_id,
                "effects": effects,
                "verticals": list(self.verticals),
                "room": self.room or None,
            },
        }
        # P8: notify resource subscribers (best-effort)
        try:
            if effects.get("regions") or self.room:
                publish_effects_invalidation(
                    room=self.room,
                    session_id=self.runner.session.session_id,
                    effects=effects,
                )
        except Exception:
            pass
        return body

    async def handle_jsonrpc(self, message: Mapping[str, Any]) -> dict[str, Any]:
        """Minimal JSON-RPC 2.0 for tools + resources + initialize."""
        mid = message.get("id")
        method = message.get("method")
        params = message.get("params") or {}

        def ok(result: Any) -> dict[str, Any]:
            return {"jsonrpc": "2.0", "id": mid, "result": result}

        def err(code: int, msg: str) -> dict[str, Any]:
            return {
                "jsonrpc": "2.0",
                "id": mid,
                "error": {"code": code, "message": msg},
            }

        if method in ("tools/list", "list_tools"):
            return ok(self.list_tools())
        if method in ("tools/call", "call_tool"):
            name = params.get("name")
            if not name:
                return err(-32602, "name required")
            arguments = params.get("arguments") or params.get("args") or {}
            conf = params.get("confirmation")
            dry = params.get("dry_run")
            out = await self.call_tool(
                name,
                arguments,
                confirmation=conf,
                dry_run=dry,
                call_id=params.get("id"),
            )
            return ok(out)
        if method in ("resources/list", "list_resources"):
            return ok(self.list_resources())
        if method in ("resources/read", "read_resource"):
            uri = params.get("uri") or params.get("url")
            if not uri:
                return err(-32602, "uri required")
            try:
                return ok(self.read_resource(str(uri)))
            except PermissionError as exc:
                return err(-32001, str(exc))
            except ValueError as exc:
                return err(-32602, str(exc))
        if method in ("resources/subscribe", "subscribe_resources"):
            uris = params.get("uris") or params.get("uri") or []
            if isinstance(uris, str):
                uris = [uris]
            return ok(
                subscribe_info(
                    room=self.room,
                    session_id=self.runner.session.session_id,
                    uris=list(uris),
                )
            )
        if method in ("initialize", "ping"):
            from ux_channel.mcp.verticals import list_verticals

            return ok(
                {
                    "protocolVersion": "2024-11-05",
                    "serverInfo": {
                        "name": "ux-channel",
                        "version": __import__(
                            "ux_channel._version", fromlist=["__version__"]
                        ).__version__,
                    },
                    "capabilities": {
                        "tools": {},
                        "resources": {},
                        "ux_channel": {
                            "effects": "1",
                            "verticals": [p.id for p in list_verticals()],
                            "sessions": True,
                            "confirmation": "token-v1",
                            "subscribe": "sse-v1",
                        },
                    },
                }
            )
        return err(-32601, f"method not found: {method}")
