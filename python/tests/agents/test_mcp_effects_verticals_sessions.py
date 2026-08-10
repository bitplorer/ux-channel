"""MCP effects envelope, vertical packs, confirm tokens, sessions, resources."""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from ux_channel import ActionRegistry, Result, toast
from ux_channel.agent_runtime import (
    AgentPolicy,
    AgentRunner,
    AgentSession,
    ToolCall,
    agent_tool,
)
from ux_channel.asgi.fastapi import mount_channel
from ux_channel.host.config import ChannelConfig
from ux_channel.mcp import (
    McpToolAdapter,
    effects_from_result,
    register_builtin_verticals,
    register_vertical,
    VerticalPack,
)
from ux_channel.mcp.confirm import mint_confirm_token, verify_confirm_token, args_hash
from ux_channel.mcp.sessions import McpSessionStore, set_session_store, get_session_store
from ux_channel.mcp.verticals import clear_verticals, filter_tools_by_verticals
from ux_channel.protocol.ops import morph


SECRET = "test-secret-key-32chars-minimum!!"


def _reg():
    reg = ActionRegistry(secret=SECRET, require_cap=True)

    @reg.action("Search.query")
    @agent_tool("Search", read_only=True, tags=("search", "vertical:pos"))
    def search(q: str = ""):
        return Result.success(
            toast(f"found:{q}"),
            morph('[data-channel-id="cart"]', "<b>1</b>"),
        )

    @reg.action("Orders.cancel")
    @agent_tool("Cancel", dangerous=True, tags=("vertical:pos",))
    def cancel(order_id: str = ""):
        return Result.success(toast(f"cancelled:{order_id}"))

    @reg.action("lab_flash")
    @agent_tool("Flash DUT", dangerous=True, tags=("vertical:lab",))
    def flash(n: int = 1):
        return Result.success(toast(f"flash:{n}"))

    return reg


def test_effects_from_result_regions_and_toasts():
    r = Result.success(
        toast("hi"),
        morph('[data-channel-id="cart"]', "<span>x</span>"),
    )
    fx = effects_from_result(r)
    assert fx["ok"] is True
    assert fx["regions"] == ["cart"]
    assert fx["toasts"][0]["message"] == "hi"
    assert fx["ops"][1]["uid"] == "cart"


def test_effects_confirmation_required():
    r = Result.failure(
        "confirmation_required",
        "need confirm",
        confirmation_required=True,
        action="Orders.cancel",
        confirm_token="tok",
    )
    fx = effects_from_result(r)
    assert fx["needs_confirmation"] is True
    assert fx["confirm_token"] == "tok"
    assert fx["ok"] is False


def test_vertical_filter():
    clear_verticals()
    register_builtin_verticals(replace=True)
    tools = [
        {"name": "pos_pay", "annotations": {"uid": {"tags": ["vertical:pos"]}}},
        {"name": "lab_flash", "annotations": {"uid": {"tags": ["vertical:lab"]}}},
        {"name": "other", "annotations": {"uid": {"tags": []}}},
    ]
    only_pos = filter_tools_by_verticals(tools, ["pos"])
    names = {t["name"] for t in only_pos}
    assert names == {"pos_pay"}


def test_confirm_token_roundtrip_and_replay():
    args = {"order_id": "1"}
    tok, exp = mint_confirm_token(
        SECRET,
        action="Orders.cancel",
        arguments=args,
        session_id="s1",
        agent_id="bot",
        ttl_s=60,
    )
    assert exp > 0
    store: set = set()
    ok, reason = verify_confirm_token(
        SECRET,
        tok,
        action="Orders.cancel",
        arguments=args,
        session_id="s1",
        agent_id="bot",
        nonce_store=store,
    )
    assert ok and reason == "ok"
    ok2, reason2 = verify_confirm_token(
        SECRET,
        tok,
        action="Orders.cancel",
        arguments=args,
        session_id="s1",
        agent_id="bot",
        nonce_store=store,
    )
    assert not ok2 and reason2 == "replay"
    # args mismatch
    tok2, _ = mint_confirm_token(
        SECRET, action="Orders.cancel", arguments=args, session_id="s1", agent_id="bot"
    )
    store2: set = set()
    bad, _ = verify_confirm_token(
        SECRET,
        tok2,
        action="Orders.cancel",
        arguments={"order_id": "2"},
        session_id="s1",
        agent_id="bot",
        nonce_store=store2,
    )
    assert not bad


def test_runner_mints_confirm_token_and_accepts_it():
    reg = _reg()
    policy = AgentPolicy.production(
        allow=["Orders.cancel", "Search.query"],
        confirm=["Orders.cancel"],
    )
    session = AgentSession(agent_id="bot", policy=policy)
    runner = AgentRunner(reg, session, confirmation_secret=SECRET)

    blocked = runner.call_tool(ToolCall(name="Orders.cancel", arguments={"order_id": "1"}))
    assert blocked.error.code == "confirmation_required"
    tok = blocked.meta.get("confirm_token")
    assert tok

    ok = runner.call_tool(
        ToolCall(
            name="Orders.cancel",
            arguments={"order_id": "1"},
            confirmation=tok,
        )
    )
    assert ok.ok


def test_mcp_adapter_effects_envelope():
    reg = _reg()
    policy = AgentPolicy.production(allow=["Search.query"])
    session = AgentSession(agent_id="bot", policy=policy)
    runner = AgentRunner(reg, session)
    adapter = McpToolAdapter(runner, verticals=("pos",))
    tools = adapter.list_tools()["tools"]
    names = {t["name"] for t in tools}
    assert "Search.query" in names
    assert "lab_flash" not in names

    out = adapter.call_tool_sync("Search.query", {"q": "x"})
    assert out["isError"] is False
    fx = out["_meta"]["effects"]
    assert "cart" in fx["regions"]
    assert fx["toasts"]


def test_http_mcp_session_and_resources():
    clear_verticals()
    register_builtin_verticals(replace=True)
    set_session_store(McpSessionStore())

    app = FastAPI()
    cfg = ChannelConfig.development(
        secret=SECRET,
        allow_memory_stores=True,
        mount_agent_mcp=True,
        agent_token="dev-token",
        agent_confirmation_secret=SECRET,
        mcp_verticals=("pos",),
        mcp_resource_regions=("cart",),
        rate_limit_per_minute=0,
        enforce_same_origin=False,
        require_channel_header=False,
    )
    reg = _reg()
    reg.config = cfg  # type: ignore[attr-defined]
    mount_channel(app, reg, config=cfg)
    app.state.uid_agent_policy = AgentPolicy.production(
        allow=["Search.query", "Orders.cancel", "lab_flash"],
        confirm=["Orders.cancel"],
    )
    c = TestClient(app)
    headers = {"Authorization": "Bearer dev-token"}

    # list tools filtered by vertical pos
    r = c.get("/ux-channel/mcp/tools", headers=headers)
    assert r.status_code == 200
    names = {t["name"] for t in r.json()["tools"]}
    assert "Search.query" in names
    assert "lab_flash" not in names

    # mint session
    r = c.post(
        "/ux-channel/mcp/session",
        headers=headers,
        json={"room": "pos", "sub": "bot-1", "scopes": ["pos"], "verticals": ["pos"]},
    )
    assert r.status_code == 200
    ticket = r.json()["ticket"]
    assert ticket

    sh = {"Authorization": f"Bearer {ticket}"}
    r = c.get("/ux-channel/mcp/tools", headers=sh)
    assert r.status_code == 200

    r = c.get("/ux-channel/mcp/resources", headers=sh)
    assert r.status_code == 200
    uris = {x["uri"] for x in r.json()["resources"]}
    assert "uid://claim" in uris
    assert "uid://verticals" in uris

    r = c.get("/ux-channel/mcp/resources/read", headers=sh, params={"uri": "uid://claim"})
    assert r.status_code == 200
    assert "pos" in r.json()["text"]

    # call with effects
    r = c.post(
        "/ux-channel/mcp/tools/call",
        headers=sh,
        json={"name": "Search.query", "arguments": {"q": "a"}},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["_meta"]["effects"]["regions"] == ["cart"]

    # confirm ladder
    r = c.post(
        "/ux-channel/mcp/tools/call",
        headers=sh,
        json={"name": "Orders.cancel", "arguments": {"order_id": "9"}},
    )
    assert r.status_code == 200  # confirmation_required not isError transport
    assert r.json()["_meta"]["effects"]["needs_confirmation"] is True
    tok = r.json()["_meta"]["effects"].get("confirm_token")
    assert tok
    r = c.post(
        "/ux-channel/mcp/tools/call",
        headers=sh,
        json={
            "name": "Orders.cancel",
            "arguments": {"order_id": "9"},
            "confirmation": tok,
        },
    )
    assert r.status_code == 200
    assert r.json()["isError"] is False

    # revoke
    r = c.post("/ux-channel/mcp/session/revoke", headers=headers, json={"ticket": ticket})
    assert r.status_code == 200
    r = c.get("/ux-channel/mcp/tools", headers=sh)
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_jsonrpc_initialize_capabilities():
    reg = _reg()
    clear_verticals()
    register_builtin_verticals(replace=True)
    policy = AgentPolicy.development()
    session = AgentSession(agent_id="bot", policy=policy)
    runner = AgentRunner(reg, session)
    adapter = McpToolAdapter(runner, verticals=("pos", "lab"))

    out = await adapter.handle_jsonrpc(
        {"jsonrpc": "2.0", "id": 1, "method": "initialize"}
    )
    caps = out["result"]["capabilities"]["ux_channel"]
    assert caps["effects"] == "1"
    assert "pos" in caps["verticals"]
    assert caps["sessions"] is True
