from __future__ import annotations
from ux_channel.agent_runtime.policy import AgentPolicy
from ux_channel.agent_runtime.runner import AgentRunner, ToolCall
from ux_channel.agent_runtime.session import AgentSession
from ux_channel.host.context import Principal
from ux_channel.host.idempotency import MemoryIdempotencyStore
from ux_channel.host.registry import ActionRegistry
from ux_channel.mcp.sessions import MemoryMcpSessionStore
from ux_channel.protocol.types import Intent
from ux_channel.security.ratelimit import MemoryRateLimiter

def test_soft_id_meta_no_roles():
    reg = ActionRegistry(secret="test-secret-key-32chars-minimum!!!!", require_cap=False)
    seen = {}
    @reg.action("X")
    def x(ctx=None):
        seen["id"] = getattr(getattr(ctx, "principal", None), "id", None)
        seen["meta"] = dict(ctx.meta or {})
        return None
    assert reg.dispatch(Intent(action="X", args={"user_id": "u", "roles": ["admin"]})).ok
    assert seen["id"] == "u" and "roles" not in seen["meta"]

def test_stores_fail_closed():
    s = MemoryIdempotencyStore(max_keys=2)
    s.set("a", {"ok": 1}, ttl_s=3600)
    s.set("b", {"ok": 1}, ttl_s=3600)
    s.set("c", {"ok": 1}, ttl_s=3600)
    assert s.get("c") is None
    lim = MemoryRateLimiter(rate_per_minute=600, burst=5, max_keys=2)
    assert lim.allow("a") and lim.allow("b") and lim.allow("c") is False

def test_mcp_session_full_raises():
    store = MemoryMcpSessionStore(max_sessions=2)
    store.create(agent_id="a", room="r", sub="s", scopes=["x"], ttl_s=900)
    store.create(agent_id="b", room="r", sub="s", scopes=["x"], ttl_s=900)
    try:
        store.create(agent_id="c", room="r", sub="s", scopes=["x"], ttl_s=900)
        assert False
    except RuntimeError as e:
        assert "full" in str(e).lower()

def test_agent_confirm_no_secret():
    reg = ActionRegistry(secret="test-secret-key-32chars-minimum!!!!", require_cap=False)
    @reg.action("Danger.do")
    def d():
        return None
    session = AgentSession(
        agent_id="a", session_id="s",
        policy=AgentPolicy(allow_actions=frozenset({"Danger.do"}), confirm_actions=frozenset({"Danger.do"})),
        principal=Principal.of("agent"),
    )
    runner = AgentRunner(reg, session, confirmation_secret=None)
    reg.config = None  # type: ignore
    assert runner._confirmed(ToolCall(name="Danger.do", arguments={}, confirmation="yes")) is False
