"""Authz seal + deeper hardening contracts — must not regress."""

from __future__ import annotations

from ux_channel.agent_runtime.policy import AgentPolicy
from ux_channel.agent_runtime.runner import AgentRunner, ToolCall
from ux_channel.agent_runtime.session import AgentSession
from ux_channel.host.config import ChannelConfig
from ux_channel.host.context import Principal
from ux_channel.host.idempotency import MemoryIdempotencyStore
from ux_channel.host.registry import ActionRegistry
from ux_channel.mcp.sessions import MemoryMcpSessionStore
from ux_channel.protocol.types import Intent
from ux_channel.security.ratelimit import MemoryRateLimiter, rate_limit_hook
from ux_channel.security.security import safe_href, sanitize_op_hrefs
from ux_channel.security.security_events import get_security_bus, set_security_bus, SecurityEventBus


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


def test_role_claim_emits_security_event():
    bus = SecurityEventBus(retain=50)
    set_security_bus(bus)
    reg = ActionRegistry(secret="test-secret-key-32chars-minimum!!!!", require_cap=False)

    @reg.action("Y")
    def y(ctx=None):
        return None

    assert reg.dispatch(Intent(action="Y", args={"user_id": "u", "roles": ["admin"]})).ok
    kinds = [e["kind"] for e in bus.recent(20)]
    assert "role_claim_ignored" in kinds


def test_cap_sub_overrides_soft_principal_from_args():
    """Signed cap.sub wins over client-supplied user_id when they disagree."""
    secret = "test-secret-key-32chars-minimum!!!!"
    reg = ActionRegistry(secret=secret, require_cap=True)
    seen = {}

    @reg.action("Who.ami")
    def who(ctx=None):
        seen["id"] = getattr(getattr(ctx, "principal", None), "id", None)
        return None

    args = {"user_id": "attacker"}
    cap = reg.mint("Who.ami", args, sub="alice")
    r = reg.dispatch(Intent(action="Who.ami", args=args, cap=cap))
    assert r.ok, r.error
    assert seen["id"] == "alice"


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
        agent_id="a",
        session_id="s",
        policy=AgentPolicy(
            allow_actions=frozenset({"Danger.do"}),
            confirm_actions=frozenset({"Danger.do"}),
        ),
        principal=Principal.of("agent"),
    )
    runner = AgentRunner(reg, session, confirmation_secret=None)
    reg.config = None  # type: ignore
    assert (
        runner._confirmed(
            ToolCall(name="Danger.do", arguments={}, confirmation="yes")
        )
        is False
    )


def test_production_ws_require_origin_default():
    cfg = ChannelConfig.production(secret="x" * 32)
    assert cfg.ws_require_origin is True
    assert cfg.webrtc_require_ticket is True
    assert cfg.webrtc_require_origin is True


def test_production_navigate_hosts_derived_from_origins():
    cfg = ChannelConfig.production(
        secret="x" * 32,
        allowed_origins=("https://app.example.com", "https://admin.example.com"),
    )
    assert "app.example.com" in cfg.navigate_allowed_hosts
    assert "admin.example.com" in cfg.navigate_allowed_hosts
    # absolute off-site blocked when hosts configured
    assert safe_href("https://evil.example/phish", allowed_hosts=cfg.navigate_allowed_hosts) is None
    assert safe_href("/relative/ok", allowed_hosts=cfg.navigate_allowed_hosts) == "/relative/ok"
    assert (
        safe_href("https://app.example.com/path", allowed_hosts=cfg.navigate_allowed_hosts)
        == "https://app.example.com/path"
    )


def test_rate_limit_emits_security_event():
    bus = SecurityEventBus(retain=50)
    set_security_bus(bus)
    lim = MemoryRateLimiter(rate_per_minute=60, burst=1, max_keys=100)
    hook = rate_limit_hook(lim)
    intent = Intent(action="Flood.x", args={})
    assert hook(intent, {}) is None
    denied = hook(intent, {})
    assert denied is not None and not denied.ok
    assert any(e["kind"] == "rate_limited" for e in bus.recent(20))


def test_sanitize_op_hrefs_blocks_js():
    ops = sanitize_op_hrefs([{"op": "navigate", "href": "javascript:alert(1)"}])
    assert ops[0]["op"] == "noop"
