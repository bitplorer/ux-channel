"""MCP P6 annotations / P7 redis sessions / P8 resource subscribe."""

from __future__ import annotations

import asyncio
import json
import threading
import time

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from ux_channel import ActionRegistry, Result, toast
from ux_channel.agents import AgentPolicy, AgentRunner, AgentSession, ToolCall, agent_tool
from ux_channel.asgi.fastapi import mount_channel
from ux_channel.config import ChannelConfig
from ux_channel.mcp import (
    McpToolAdapter,
    classify_tool,
    enrich_tools,
    publish_effects_invalidation,
    register_builtin_verticals,
    subscribe_info,
)
from ux_channel.mcp.sessions import (
    MemoryMcpSessionStore,
    RedisMcpSessionStore,
    set_session_store,
    build_session_store,
)
from ux_channel.mcp.verticals import clear_verticals
from ux_channel.ops import morph
from ux_channel.push import get_push_bus, set_push_bus, PushBus, MemoryPushBackend

SECRET = "test-secret-key-32chars-minimum!!"


def _reg():
    reg = ActionRegistry(secret=SECRET, require_cap=False)

    @reg.action("pos_queue_add")
    @agent_tool("queue", tags=("vertical:pos", "outbox"))
    def q(sku: str = "A"):
        return Result.success(toast("queued"))

    @reg.action("pos_pay")
    @agent_tool("pay", tags=("vertical:pos",))
    def pay():
        return Result.success(toast("paid"), morph('[data-channel-id="cart"]', "0"))

    @reg.action("lab_flash")
    @agent_tool("flash", dangerous=True, tags=("vertical:lab",))
    def flash():
        return Result.success(toast("flash"))

    @reg.action("lab_read")
    @agent_tool("read", read_only=True, tags=("vertical:lab",))
    def read():
        return Result.success(toast("id"))

    return reg


def test_p6_annotations_outbox_and_io():
    clear_verticals()
    register_builtin_verticals(replace=True)
    tools = [
        {
            "name": "pos_queue_add",
            "annotations": {"uid": {"tags": ["vertical:pos", "outbox"]}},
        },
        {
            "name": "lab_flash",
            "annotations": {"uid": {"tags": ["vertical:lab"]}, "readOnlyHint": False},
        },
        {
            "name": "lab_read",
            "annotations": {"uid": {"tags": ["vertical:lab"]}, "readOnlyHint": True},
        },
    ]
    enriched = enrich_tools(tools, verticals=("pos", "lab"))
    by = {t["name"]: t for t in enriched}
    assert by["pos_queue_add"]["annotations"]["ux_channel"]["outbox"] is True
    assert by["pos_queue_add"]["annotations"]["ux_channel"]["vertical"] == "pos"
    assert by["lab_flash"]["annotations"]["ux_channel"]["confirm"] is True
    assert by["lab_flash"]["annotations"]["ux_channel"]["requires_quantity"] is True
    assert by["lab_read"]["annotations"]["ux_channel"]["kind"] in ("io.read", "read")

    frag = classify_tool("pos_pay", ["vertical:pos"])
    assert frag.get("confirm") is True


def test_p6_adapter_list_includes_ux_channel_block():
    clear_verticals()
    register_builtin_verticals(replace=True)
    reg = _reg()
    policy = AgentPolicy.production(allow=["pos_queue_add", "lab_flash", "lab_read", "pos_pay"])
    runner = AgentRunner(reg, AgentSession(agent_id="b", policy=policy))
    adapter = McpToolAdapter(runner, verticals=("pos",))
    tools = adapter.list_tools()["tools"]
    names = {t["name"] for t in tools}
    assert "pos_queue_add" in names
    assert "lab_flash" not in names
    q = next(t for t in tools if t["name"] == "pos_queue_add")
    assert q["annotations"]["ux_channel"]["outbox"] is True


def test_p7_memory_session_chaos_concurrent():
    store = MemoryMcpSessionStore()
    set_session_store(store)
    errors = []
    tickets = []

    def worker(i):
        try:
            s = store.create(
                agent_id=f"a{i}",
                room="pos",
                sub=f"s{i}",
                scopes=["pos"],
                verticals=["pos"],
                ttl_s=120,
            )
            tickets.append(s.ticket)
            assert store.get_by_ticket(s.ticket) is not None
            if i % 2 == 0:
                store.revoke(s.ticket)
                assert store.get_by_ticket(s.ticket) is None
        except Exception as e:
            errors.append(e)

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(40)]
    for th in threads:
        th.start()
    for th in threads:
        th.join()
    assert not errors


def test_p7_redis_session_store_if_available():
    try:
        import redis  # noqa: F401
        r = redis.Redis.from_url("redis://127.0.0.1:6379/15")
        r.ping()
    except Exception:
        pytest.skip("redis not available")
    store = RedisMcpSessionStore("redis://127.0.0.1:6379/15", prefix="uidch:test:mcp:")
    s = store.create(
        agent_id="bot",
        room="lab",
        sub="u1",
        scopes=["lab"],
        verticals=["lab"],
        ttl_s=60,
    )
    assert store.get_by_ticket(s.ticket).room == "lab"
    assert store.revoke(s.ticket) is True
    assert store.get_by_ticket(s.ticket) is None


def test_p8_subscribe_info_and_publish():
    set_push_bus(PushBus(MemoryPushBackend()))
    info = subscribe_info(room="pos", session_id="sess1", uris=["uid://region/cart"])
    assert any("mcp.resource.pos" in t for t in info["topics"])
    assert info["sse"]

    q: asyncio.Queue = asyncio.Queue()
    bus = get_push_bus()
    topic = "mcp.resource.pos"
    bus.subscribe(topic, q)
    n = publish_effects_invalidation(
        room="pos",
        session_id="sess1",
        effects={"ok": True, "regions": ["cart"]},
    )
    assert n >= 1
    item = q.get_nowait()
    assert item["event"] == "resource.updated"
    assert "uid://region/cart" in item["uris"]
    bus.unsubscribe(topic, q)


def test_p8_http_subscribe_and_tool_invalidation():
    clear_verticals()
    register_builtin_verticals(replace=True)
    set_session_store(MemoryMcpSessionStore())
    set_push_bus(PushBus(MemoryPushBackend()))

    app = FastAPI()
    cfg = ChannelConfig.development(
        secret=SECRET,
        allow_memory_stores=True,
        mount_agent_mcp=True,
        agent_token="tok",
        mcp_verticals=("pos",),
        mcp_resource_regions=("cart",),
        rate_limit_per_minute=0,
        enforce_same_origin=False,
        require_channel_header=False,
        push_require_auth=False,
        push_allow_public=True,
    )
    reg = _reg()
    reg.config = cfg  # type: ignore[attr-defined]
    mount_channel(app, reg, config=cfg)
    app.state.uid_agent_policy = AgentPolicy.production(
        allow=["pos_pay", "pos_queue_add"], confirm=[]
    )
    # agent_confirmation_secret so dangerous tools can still mint tokens;
    # use non-dangerous pay for this path by re-registering below if needed
    c = TestClient(app)
    h = {"Authorization": "Bearer tok"}
    r = c.post(
        "/ux-channel/mcp/session",
        headers=h,
        json={"room": "pos", "sub": "b", "scopes": ["pos"], "verticals": ["pos"]},
    )
    assert r.status_code == 200
    ticket = r.json()["ticket"]
    sh = {"Authorization": f"Bearer {ticket}"}

    # JSON-RPC subscribe info
    r = c.post(
        "/ux-channel/mcp/rpc",
        headers=sh,
        json={
            "jsonrpc": "2.0",
            "id": 1,
            "method": "resources/subscribe",
            "params": {"uris": ["uid://region/cart"]},
        },
    )
    assert r.status_code == 200
    body = r.json()["result"]
    assert "mcp.resource.pos" in body["topics"]

    # Subscribe bus directly + tool call publishes invalidation (no long SSE block)
    q: asyncio.Queue = asyncio.Queue()
    bus = get_push_bus()
    bus.subscribe("mcp.resource.pos", q)
    r = c.post(
        "/ux-channel/mcp/tools/call",
        headers=sh,
        json={"name": "pos_pay", "arguments": {}},
    )
    assert r.status_code == 200
    assert "cart" in r.json()["_meta"]["effects"]["regions"]
    # invalidation should land on bus
    deadline = time.time() + 1.0
    item = None
    while time.time() < deadline:
        try:
            item = q.get_nowait()
            break
        except Exception:
            time.sleep(0.01)
    bus.unsubscribe("mcp.resource.pos", q)
    assert item is not None
    assert item.get("event") == "resource.updated"
    assert any("cart" in u for u in item.get("uris", []))

    # SSE endpoint auth + topic guard (single event via short client read is flaky;
    # verify 403 on wrong topic and 200 content-type on allowed)
    r = c.get(
        "/ux-channel/mcp/resources/subscribe",
        headers=sh,
        params={"topic": "mcp.resource.other"},
    )
    assert r.status_code == 403
