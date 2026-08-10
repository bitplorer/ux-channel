"""Waves 1–5 — production stores, live, region state, policy, security events."""

from __future__ import annotations

import uuid

from fastapi import FastAPI

from ux_channel import Channel, ChannelConfig, Region
from ux_channel.policy import PolicyEngine, set_policy
from ux_channel.push_security import authorize_push_subscribe, sign_push_ticket
from ux_channel.security import safe_href
from ux_channel.security_events import (
    SecurityEventBus,
    get_security_bus,
    set_security_bus,
)
from ux_channel.ticket_revoke import (
    TicketRevocationList,
    get_revocation_list,
    set_revocation_list,
)
from ux_channel.ws_limits import WsRateLimiter, set_ws_limiter


def _ch(**kw):
    app = FastAPI()
    cfg = ChannelConfig.development(
        secret="dev-secret-key-32chars-minimum!!!!",
        allow_memory_stores=True,
        **kw,
    )
    return Channel.boot(app, config=cfg), app


def test_navigate_host_allowlist():
    assert safe_href("/app") == "/app"
    assert safe_href("https://evil.com/x", allowed_hosts=("good.com",)) is None
    assert (
        safe_href("https://good.com/x", allowed_hosts=("good.com",))
        == "https://good.com/x"
    )
    assert (
        safe_href("https://sub.good.com/x", allowed_hosts=("good.com",))
        == "https://sub.good.com/x"
    )


def test_navigate_allowlist_in_dispatch():
    ch, _ = _ch(navigate_allowed_hosts=("good.com",))

    @ch.on(name="Go.away")
    def go():
        return ch.done(navigate="https://evil.com/phish")

    cap = ch.registry.mint("Go.away", {})
    r = ch.registry.dispatch({"v": "1", "action": "Go.away", "args": {}, "cap": cap})
    if r.ok:
        hrefs = [o.get("href") for o in (r.ops or []) if o.get("op") == "navigate"]
        assert not any(h and "evil" in str(h) for h in hrefs)


def test_ticket_revoke():
    ch, _ = _ch()
    prev = get_revocation_list()
    try:
        rl = TicketRevocationList()
        set_revocation_list(rl)
        ticket = sign_push_ticket(ch.config, topic="shop.private", sub="u1")
        ok1 = authorize_push_subscribe(ch.config, topic="shop.private", ticket=ticket)
        assert ok1 is True or (isinstance(ok1, tuple) and ok1[0] is True)
        rl.revoke(ticket, ttl_s=3600)
        assert rl.is_revoked(ticket)
        ok2 = authorize_push_subscribe(ch.config, topic="shop.private", ticket=ticket)
        denied = ok2 is False or (isinstance(ok2, tuple) and ok2[0] is False)
        assert denied
    finally:
        set_revocation_list(prev)


def test_security_events_bus():
    bus = SecurityEventBus(retain=50)
    prev = get_security_bus()
    try:
        set_security_bus(bus)
        bus.emit("cap_fail", action="X.y", reason="bad")
        recent = list(bus.recent())
        assert len(recent) >= 1
        bus.clear()
        assert len(list(bus.recent())) == 0
    finally:
        set_security_bus(prev)


def test_ws_rate_limiter():
    lim = WsRateLimiter(max_connect_per_minute=2, max_messages_per_minute=100)
    set_ws_limiter(lim)
    ok1, _ = lim.allow_connect("ip1")
    ok2, _ = lim.allow_connect("ip1")
    ok3, _ = lim.allow_connect("ip1")
    assert ok1 and ok2 and not ok3


def test_config_with_redis_and_hosts():
    cfg = ChannelConfig.production(
        "xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
        allow_memory_stores=True,
    ).with_navigate_hosts("app.example", "cdn.example")
    hosts = cfg.navigate_allowed_hosts or ()
    assert "app.example" in hosts
    cfg2 = cfg.with_redis("redis://localhost:6379/0")
    assert cfg2 is not None


def test_live_bind_and_publish():
    ch, _ = _ch()

    class T(Region):
        def render(self, ctx):
            return f"<b>{self.uid}</b>"

    t = T(ch, uid="live.t").mount()
    ch.live.bind("public.demo", t)
    n = ch.live.publish("public.demo")
    assert n >= 0
    assert ch.live.regions_for("public.demo") == ["live.t"]
    assert "public.demo" in ch.diagnose()["live_bindings"]


def test_live_presence():
    ch, _ = _ch()
    topic = f"public.presence.{uuid.uuid4().hex[:12]}"
    assert ch.live.presence_touch(topic, "c1") == 1
    assert ch.live.presence_touch(topic, "c2") == 2
    assert ch.live.presence_count(topic) == 2


def test_region_broadcast_meta():
    ch, _ = _ch()

    class C(Region):
        def render(self, ctx):
            return f'<i>{self.state_get("n", 0)}</i>'

        @Region.action(broadcast="public.board")
        def bump(self):
            self.state_change("n", lambda n: (n or 0) + 1, default=0)

    c = C(ch, uid="c").mount()
    ch.live.bind("public.board", c)
    cap = ch.registry.mint("c.bump", {})
    r = ch.registry.dispatch({"v": "1", "action": "c.bump", "args": {}, "cap": cap})
    assert r.ok
    assert c.state_get("n") == 1


def test_region_state_namespace():
    ch, _ = _ch()

    class A(Region):
        def render(self, ctx):
            return str(self.state_get("x", 0))

    a = A(ch, uid="a1").mount()
    b = A(ch, uid="a2").mount()
    a.state_set("x", 1)
    b.state_set("x", 2)
    assert a.state_get("x") == 1
    assert b.state_get("x") == 2


def test_policy_engine_denies_action():
    ch, _ = _ch()
    eng = PolicyEngine()
    eng.allow_action(
        lambda intent, principal: getattr(intent, "action", "") != "Nope.x"
    )
    set_policy(eng)

    @ch.on(name="Nope.x")
    def nope():
        return ch.done(notice="should not")

    @ch.on(name="Ok.y")
    def ok():
        return ch.done(notice="ok")

    cap_n = ch.registry.mint("Nope.x", {})
    r1 = ch.registry.dispatch({"v": "1", "action": "Nope.x", "args": {}, "cap": cap_n})
    assert not r1.ok
    assert r1.error is not None

    cap_o = ch.registry.mint("Ok.y", {})
    r2 = ch.registry.dispatch({"v": "1", "action": "Ok.y", "args": {}, "cap": cap_o})
    assert r2.ok


def test_ch_revoke_ticket_api():
    ch, _ = _ch()
    tok = ch.webrtc.sign_ticket(room="shop.x", sub="p1")
    ch.revoke_ticket(tok)


def test_wire_contract_result_shape():
    """Wave 4: Intent/Result golden shape."""
    ch, _ = _ch()

    @ch.on(name="Ping.hi")
    def hi():
        return ch.done(notice="hi")

    cap = ch.registry.mint("Ping.hi", {})
    r = ch.registry.dispatch({"v": "1", "action": "Ping.hi", "args": {}, "cap": cap})
    if hasattr(r, "as_dict"):
        d = r.as_dict()
    elif hasattr(r, "to_dict"):
        d = r.to_dict()
    else:
        d = {"ok": r.ok, "ops": list(r.ops or [])}
    assert "ops" in d and isinstance(d["ops"], list)
    assert d.get("ok") is True
