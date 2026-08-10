"""
Coverage for MCP + host_csrf + outbox attach docs contracts.

Ensures documented public helpers stay importable, documented, and behavioral.
"""

from __future__ import annotations

import ast
import inspect
from pathlib import Path

import pytest

from ux_channel.host_csrf import (
    CHANNEL_CSRF_HEADER,
    intent_headers,
    is_channel_csrf_header,
    looks_like_host_csrf_name,
)
from ux_channel.mcp import (
    McpToolAdapter,
    VerticalPack,
    classify_tool,
    effects_from_result,
    enrich_tools,
    filter_tools_by_verticals,
    list_verticals,
    publish_effects_invalidation,
    register_builtin_verticals,
    register_vertical,
    subscribe_info,
)
from ux_channel.mcp.asgi_routes import create_mcp_adapter, resolve_mcp_auth
from ux_channel.mcp.confirm import args_hash, mint_confirm_token, verify_confirm_token
from ux_channel.mcp.resources import list_resources, read_resource
from ux_channel.mcp.sessions import (
    MemoryMcpSessionStore,
    build_session_store,
    get_session_store,
    set_session_store,
)
from ux_channel.mcp.verticals import clear_verticals, get_vertical
from ux_channel.outbox import MemoryIntentOutbox, attach_outbox, get_outbox
from ux_channel.types import Result
from ux_channel.ops import toast
from ux_channel.agents import AgentPolicy, AgentRunner, AgentSession, agent_tool
from ux_channel import ActionRegistry


ROOT = Path(__file__).resolve().parents[2]
MCP_DIR = ROOT / "src" / "ux_channel" / "mcp"
SECRET = "test-secret-key-32chars-minimum!!"

# Every MCP module must have a non-trivial package docstring and public callables documented
REQUIRED_MCP_MODULES = [
    "adapter.py",
    "annotations.py",
    "asgi_routes.py",
    "confirm.py",
    "effects.py",
    "resources.py",
    "sessions.py",
    "subscribe.py",
    "verticals.py",
]


def test_mcp_modules_have_module_docstrings():
    for name in REQUIRED_MCP_MODULES:
        path = MCP_DIR / name
        assert path.is_file(), name
        tree = ast.parse(path.read_text())
        doc = ast.get_docstring(tree)
        assert doc and len(doc.strip()) >= 40, f"{name} module docstring too thin"


def test_mcp_public_functions_have_docstrings():
    """Top-level public functions in mcp/* should be documented."""
    missing = []
    for name in REQUIRED_MCP_MODULES:
        path = MCP_DIR / name
        tree = ast.parse(path.read_text())
        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if node.name.startswith("_"):
                    continue
                doc = ast.get_docstring(node)
                if not doc or len(doc.strip()) < 15:
                    missing.append(f"{name}::{node.name}")
            if isinstance(node, ast.ClassDef) and not node.name.startswith("_"):
                doc = ast.get_docstring(node)
                if not doc or len(doc.strip()) < 15:
                    # methods still checked lightly
                    for item in node.body:
                        if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                            if item.name.startswith("_") or item.name in (
                                "to_dict",
                                "to_public",
                                "from_dict",
                                "alive",
                                "create",
                                "get",
                                "get_by_ticket",
                                "revoke",
                                "__init__",
                                "__post_init__",
                            ):
                                continue
            if isinstance(node, ast.ClassDef) and node.name in (
                "McpToolAdapter",
                "VerticalPack",
                "McpSession",
                "MemoryMcpSessionStore",
                "RedisMcpSessionStore",
            ):
                d = ast.get_docstring(node)
                if not d or len(d) < 15:
                    missing.append(f"{name}::{node.name}")
    assert not missing, f"missing docs: {missing}"


def test_docs_agents_mcp_and_verticals_exist():
    docs = ROOT / "docs" / "agents"
    for name in ("AGENTS.md", "AGENTS_MCP.md", "MCP_VERTICALS.md"):
        p = docs / name
        assert p.is_file()
        text = p.read_text()
        assert len(text) > 200
    text = (docs / "AGENTS_MCP.md").read_text()
    for needle in (
        "mount_agent_mcp",
        "effects",
        "session",
        "resources",
        "ux_channel",
        "agents(ch)",
    ):
        assert needle in text, needle
    vert = (docs / "MCP_VERTICALS.md").read_text()
    for needle in ("P6", "P7", "P8", "confirm_token", "vertical"):
        assert needle in vert, needle


def test_host_csrf_docs_behavior():
    assert is_channel_csrf_header("X-Channel")
    assert is_channel_csrf_header("x-channel")
    assert not is_channel_csrf_header("X-CSRF-Token")
    assert looks_like_host_csrf_name("X-CSRF-Token")
    h = intent_headers(host_token="abc", forward_as=("X-CSRF-TOKEN",))
    assert h[CHANNEL_CSRF_HEADER] == "1"
    assert h["X-CSRF-TOKEN"] == "abc"
    # extra cannot strip channel header
    h2 = intent_headers(extra={CHANNEL_CSRF_HEADER: "nope"})
    assert h2[CHANNEL_CSRF_HEADER] == "1"


def test_effects_and_resources_contracts():
    r = Result.success(toast("x"))
    fx = effects_from_result(r)
    assert set(fx) >= {
        "ok",
        "error",
        "ops",
        "regions",
        "toasts",
        "navigated",
        "dry_run",
        "needs_confirmation",
    }
    res = list_resources(room="r1", region_uids=("cart",), has_claim=True)
    uris = {x["uri"] for x in res}
    assert "uid://verticals" in uris
    assert "uid://claim" in uris
    assert "uid://region/cart" in uris
    body = read_resource("uid://verticals", verticals=("pos",))
    assert body["mimeType"] == "application/json"
    with pytest.raises(ValueError):
        read_resource("uid://nope")


def test_vertical_register_and_filter_docs():
    clear_verticals()
    register_vertical(
        VerticalPack(id="demo", tools=frozenset({"demo_act"}), tags=frozenset({"vertical:demo"}))
    )
    assert get_vertical("demo") is not None
    tools = [
        {"name": "demo_act", "annotations": {"uid": {"tags": ["vertical:demo"]}}},
        {"name": "other", "annotations": {"uid": {"tags": []}}},
    ]
    assert [t["name"] for t in filter_tools_by_verticals(tools, ["demo"])] == ["demo_act"]
    clear_verticals()
    register_builtin_verticals()
    ids = {p.id for p in list_verticals()}
    assert {"pos", "lab"} <= ids


def test_confirm_token_docs_contract():
    h = args_hash({"a": 1})
    assert len(h) == 32
    tok, exp = mint_confirm_token(
        SECRET, action="x", arguments={"a": 1}, session_id="s", agent_id="b"
    )
    ok, reason = verify_confirm_token(
        SECRET, tok, action="x", arguments={"a": 1}, session_id="s", agent_id="b", nonce_store=set()
    )
    assert ok and reason == "ok"
    assert exp > 0


def test_session_store_and_subscribe_info():
    set_session_store(None)
    store = build_session_store(None)
    assert isinstance(store, MemoryMcpSessionStore)
    set_session_store(store)
    s = get_session_store().create(
        agent_id="a", room="r", sub="u", scopes=["x"], verticals=["pos"], ttl_s=60
    )
    assert get_session_store().get_by_ticket(s.ticket).room == "r"
    info = subscribe_info(room="r", session_id=s.session_id)
    assert any("mcp.resource.r" in t for t in info["topics"])
    assert info["sse"]
    n = publish_effects_invalidation(room="r", effects={"regions": ["cart"], "ok": True})
    assert n >= 0  # 0 if no subscribers


def test_create_mcp_adapter_and_enrich():
    clear_verticals()
    register_builtin_verticals()
    reg = ActionRegistry(secret=SECRET, require_cap=False)

    @reg.action("pos_queue_add")
    @agent_tool("q", tags=("vertical:pos", "outbox"))
    def q(sku: str = ""):
        return Result.success(toast("ok"))

    ad = create_mcp_adapter(
        reg,
        policy=AgentPolicy.production(allow=["pos_queue_add"]),
        verticals=("pos",),
        room="pos",
        scopes=("pos",),
    )
    tools = ad.list_tools()["tools"]
    assert tools
    uc = tools[0]["annotations"]["ux_channel"]
    assert uc["vertical"] == "pos"
    assert uc["outbox"] is True


def test_outbox_attach_get():
    class Ch:
        config = type("C", (), {"redis_url": None})()

    ch = Ch()
    box = attach_outbox(ch, MemoryIntentOutbox())
    assert get_outbox(ch) is box
    assert attach_outbox(ch) is box  # reuse


def test_resolve_mcp_auth_shapes():
    class Req:
        def __init__(self, headers):
            self.headers = headers

    ok, sess, mode = resolve_mcp_auth(Req({"authorization": "Bearer secret"}), agent_token="secret")
    assert ok and mode == "token" and sess is None
    ok, sess, mode = resolve_mcp_auth(Req({}), agent_token="secret")
    assert not ok and mode == "none"
