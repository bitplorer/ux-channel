"""AI agents + MCP modular surface tests."""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from ux_channel import ActionRegistry, Result, toast
from ux_channel.agent_runtime import (
    AgentPolicy,
    AgentRunner,
    AgentSession,
    MemoryAuditSink,
    ToolCall,
    agent_tool,
    tools_from_registry,
)
from ux_channel.host.config import ChannelConfig
from ux_channel.mcp import McpToolAdapter
from ux_channel.protocol.types import Intent


def _reg():
    reg = ActionRegistry(secret="test-secret-key-32chars-minimum!!", require_cap=True)

    @reg.action("Search.query")
    @agent_tool("Search knowledge base", read_only=True, tags=("search",))
    def search(q: str = ""):
        return Result.success(toast(f"found:{q}"))

    @reg.action("Orders.cancel")
    @agent_tool("Cancel order", dangerous=True)
    def cancel(order_id: str = ""):
        return Result.success(toast(f"cancelled:{order_id}"))

    @reg.action("Internal.secret")
    def secret():
        return Result.success(toast("nope"))

    return reg


def test_tools_from_registry_marked_only():
    reg = _reg()
    tools = tools_from_registry(reg, only_marked=True)
    names = {t["name"] for t in tools}
    assert "Search.query" in names
    assert "Orders.cancel" in names
    assert "Internal.secret" not in names
    search = next(t for t in tools if t["name"] == "Search.query")
    assert search["annotations"]["readOnlyHint"] is True
    assert "q" in search["inputSchema"]["properties"]


def test_policy_fail_closed():
    with pytest.raises(ValueError):
        AgentPolicy.production(allow=[])
    p = AgentPolicy.production(allow=["Search.query"], confirm=["Orders.cancel"])
    assert p.allows("Search.query")
    assert not p.allows("Internal.secret")
    assert p.needs_confirmation("Orders.cancel")


def test_agent_runner_allow_and_deny():
    reg = _reg()
    policy = AgentPolicy.production(allow=["Search.query"], confirm=["Orders.cancel"])
    session = AgentSession(agent_id="bot", policy=policy)
    audit = MemoryAuditSink()
    runner = AgentRunner(reg, session, audit=audit)

    r = runner.call_tool(ToolCall(name="Search.query", arguments={"q": "uid"}))
    assert r.ok
    assert "found:uid" in r.ops[0]["message"]

    denied = runner.call_tool(ToolCall(name="Internal.secret", arguments={}))
    assert not denied.ok
    assert denied.error.code == "forbidden"

    need = runner.call_tool(
        ToolCall(name="Orders.cancel", arguments={"order_id": "1"})
    )
    # Orders.cancel not in allow list
    assert not need.ok


def test_agent_confirmation_and_budget():
    reg = _reg()
    policy = AgentPolicy.production(
        allow=["Orders.cancel", "Search.query"],
        confirm=["Orders.cancel"],
        max_calls_per_session=2,
    )
    session = AgentSession(agent_id="bot", policy=policy)
    secret = "confirm-secret-key-32chars-minimum!!"
    runner = AgentRunner(reg, session, confirmation_secret=secret)

    blocked = runner.call_tool(
        ToolCall(name="Orders.cancel", arguments={"order_id": "1"})
    )
    assert blocked.error.code == "confirmation_required"
    tok = (blocked.meta or {}).get("confirm_token")
    assert tok, "expected signed confirm_token in failure meta"

    ok = runner.call_tool(
        ToolCall(
            name="Orders.cancel",
            arguments={"order_id": "1"},
            confirmation=tok,
        )
    )
    assert ok.ok

    runner.call_tool(ToolCall(name="Search.query", arguments={"q": "a"}))
    over = runner.call_tool(ToolCall(name="Search.query", arguments={"q": "b"}))
    assert over.error.code == "agent_budget_session"


@pytest.mark.asyncio
async def test_mcp_adapter_jsonrpc():
    reg = _reg()
    policy = AgentPolicy.production(allow=["Search.query"])
    session = AgentSession(agent_id="mcp", policy=policy)
    runner = AgentRunner(reg, session)
    adapter = McpToolAdapter(runner, only_marked=True)

    listed = adapter.list_tools()
    assert any(t["name"] == "Search.query" for t in listed["tools"])

    rpc = await adapter.handle_jsonrpc(
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {"name": "Search.query", "arguments": {"q": "hi"}},
        }
    )
    assert rpc["result"]["isError"] is False
    assert rpc["result"]["structuredContent"]["ok"] is True


def test_dry_run():
    reg = _reg()
    policy = AgentPolicy.production(allow=["Search.query"])
    session = AgentSession(agent_id="bot", policy=policy)
    runner = AgentRunner(reg, session)
    r = runner.call_tool(
        ToolCall(name="Search.query", arguments={"q": "x"}, dry_run=True)
    )
    assert r.ok and r.meta.get("dry_run") is True
    assert r.meta.get("would_call") == "Search.query"


def test_http_mcp_mount():
    reg = _reg()
    cfg = ChannelConfig.development(
        secret="test-secret-key-32chars-minimum!!",
        enforce_same_origin=False,
        rate_limit_per_minute=0,
        mount_agent_mcp=True,
        agent_token="agent-secret",
    )
    app = FastAPI()
    from ux_channel.agent_runtime.policy import AgentPolicy

    app.state.uid_agent_policy = AgentPolicy.production(allow=["Search.query"])
    # re-create registry with same secret and actions - mount uses reg
    from ux_channel.asgi.fastapi import mount_channel

    # need registry from_config with same actions
    reg2 = ActionRegistry.from_config(cfg)
    # copy actions
    for n in reg.names():
        reg2.replace(n, reg.get(n))

    mount_channel(app, reg2, config=cfg, mount_agent_mcp=True)
    client = TestClient(app)

    denied = client.get("/ux-channel/mcp/tools")
    assert denied.status_code == 401

    ok = client.get(
        "/ux-channel/mcp/tools",
        headers={"Authorization": "Bearer agent-secret"},
    )
    assert ok.status_code == 200
    assert any(t["name"] == "Search.query" for t in ok.json()["tools"])

    call = client.post(
        "/ux-channel/mcp/tools/call",
        headers={"Authorization": "Bearer agent-secret", "X-Channel-Agent-Id": "t1"},
        json={"name": "Search.query", "arguments": {"q": "z"}},
    )
    assert call.status_code == 200
    assert call.json()["structuredContent"]["ok"] is True
