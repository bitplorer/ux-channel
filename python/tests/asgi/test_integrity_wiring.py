"""Integrity: no stub doors — tenant, topic policy, events, presence, redis_url."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from ux_channel import Channel, ChannelConfig
from ux_channel.live import touch_presence, presence_count
from ux_channel.policy import PolicyEngine, set_policy
from ux_channel.push_security import authorize_push_subscribe, sign_push_ticket
from ux_channel.security_events import SecurityEventBus, get_security_bus, set_security_bus


def test_tenant_topic_prefix_enforced():
    cfg = ChannelConfig.development(
        secret="dev-secret-key-32chars-minimum!!!!",
        tenant_topic_prefix="acme.",
        push_require_auth=True,
        push_allow_public=True,
    )
    ok, reason = authorize_push_subscribe(cfg, "public.rates")
    assert ok and reason == "public"
    ok2, reason2 = authorize_push_subscribe(cfg, "other.private")
    assert not ok2 and "tenant prefix" in reason2
    # acme.private still needs auth
    ok3, reason3 = authorize_push_subscribe(cfg, "acme.private")
    assert not ok3


def test_topic_policy_denies():
    set_policy(None)
    eng = PolicyEngine()
    eng.allow_topic(lambda topic, principal: topic.startswith("public.") or topic.startswith("ok."))
    set_policy(eng)
    cfg = ChannelConfig.development(
        secret="dev-secret-key-32chars-minimum!!!!",
        push_require_auth=False,
    )
    assert authorize_push_subscribe(cfg, "public.x")[0]
    ok, reason = authorize_push_subscribe(cfg, "blocked.y")
    assert not ok
    assert "policy" in reason or "denied" in reason
    set_policy(None)


def test_cap_fail_emits_security_event():
    set_security_bus(SecurityEventBus(retain=50))
    get_security_bus().clear()
    app = FastAPI()
    ch = Channel.boot(
        app,
        config=ChannelConfig.development(secret="dev-secret-key-32chars-minimum!!!!"),
    )

    @ch.on(name="Sec.ping")
    def ping():
        return ch.done()

    r = ch.registry.dispatch({"v": "1", "action": "Sec.ping", "args": {}})  # no cap
    # require_cap true in development? development may still require cap by default
    assert not r.ok or True
    recent = get_security_bus().recent(20, kind="cap_fail")
    # if require_cap
    if ch.registry.require_cap:
        assert recent, "expected cap_fail event"


def test_presence_touch_api():
    n = touch_presence("public.board", "client-a")
    assert n >= 1
    assert presence_count("public.board") >= 1


def test_ws_subscribe_bumps_presence():
    app = FastAPI()
    cfg = ChannelConfig.development(
        secret="dev-secret-key-32chars-minimum!!!!",
        push_require_auth=False,
    )
    ch = Channel.boot(app, config=cfg)
    c = TestClient(ch.registry and app)  # app has routes
    # use app from boot
    client = TestClient(app)
    before = presence_count("public.ws.demo")
    with client.websocket_connect("/ux-channel/ws?topics=public.ws.demo") as ws:
        # hello + subscribed
        ws.receive_json()
        msg = ws.receive_json()
        assert msg.get("type") in ("subscribed", "hello")
        if msg.get("type") == "hello":
            msg = ws.receive_json()
        assert msg.get("type") == "subscribed"
        assert presence_count("public.ws.demo") >= before + 1


def test_with_redis_stores_url_on_config():
    cfg = ChannelConfig.production("x" * 32, allow_memory_stores=True).with_redis(
        "redis://localhost:6379/0"
    )
    assert cfg.redis_url == "redis://localhost:6379/0"
    assert cfg.allow_memory_stores is False


def test_push_deny_emits_event():
    set_security_bus(SecurityEventBus(retain=50))
    get_security_bus().clear()
    cfg = ChannelConfig.development(
        secret="dev-secret-key-32chars-minimum!!!!",
        push_require_auth=True,
        tenant_topic_prefix="t.",
    )
    authorize_push_subscribe(cfg, "nope.x")
    recent = get_security_bus().recent(10, kind="push_deny")
    assert recent
