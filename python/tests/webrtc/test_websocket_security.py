"""Production WebSocket security — connect, origin, subscribe, intent."""

from __future__ import annotations

import json

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from ux_channel import Channel, ChannelConfig, Result, morph, toast
from ux_channel.demo import attr_string, demo_button, demo_page, demo_scripts, script_tags
from ux_channel.asgi.fastapi import mount_channel
from ux_channel.push import get_push_bus
from ux_channel.push_security import sign_push_ticket
from ux_channel.registry import ActionRegistry
from ux_channel.ws_security import (
    authorize_ws_connect,
    authorize_ws_subscribe,
    check_ws_origin,
)

PROD_SECRET = "prod-secret-key-32chars-minimum!!!!"
DEV_SECRET = "dev-secret-key-32chars-minimum!!!!"


def _app(**kwargs):
    cfg = ChannelConfig.production(
        secret=PROD_SECRET,
        allow_memory_stores=True,
        enforce_same_origin=False,
        require_channel_header=False,
        rate_limit_per_minute=0,
        **kwargs,
    )
    app = FastAPI()
    reg = ActionRegistry.from_config(cfg)

    @reg.action("Ping.hi")
    def hi(n: int = 0):
        return Result.success(toast(f"hi-{n}"))

    mount_channel(app, reg, config=cfg)
    return app, cfg, reg


def test_authorize_ws_connect_fail_closed():
    cfg = ChannelConfig.production(secret=PROD_SECRET)
    ok, reason = authorize_ws_connect(cfg)
    assert ok is False
    assert "required" in reason or "authorization" in reason


def test_authorize_ws_connect_token_and_ticket():
    cfg = ChannelConfig.production(secret=PROD_SECRET, push_token="ws-tok")
    assert authorize_ws_connect(cfg, token="ws-tok")[0]
    ticket = sign_push_ticket(cfg, "shop.x")
    assert authorize_ws_connect(cfg, ticket=ticket)[0]
    # initial private topic without creds
    assert authorize_ws_connect(cfg, initial_topics=["private.x"])[0] is False
    assert authorize_ws_connect(cfg, token="ws-tok", initial_topics=["private.x"])[0]
    assert authorize_ws_connect(cfg, initial_topics=["public.rates"])[0]


def test_authorize_ws_subscribe_matches_sse():
    cfg = ChannelConfig.production(secret=PROD_SECRET)
    assert authorize_ws_subscribe(cfg, "public.a")[0]
    assert authorize_ws_subscribe(cfg, "secret.b")[0] is False
    t = sign_push_ticket(cfg, "secret.b")
    assert authorize_ws_subscribe(cfg, "secret.b", ticket=t)[0]


def test_check_ws_origin_null_denied():
    cfg = ChannelConfig.production(secret=PROD_SECRET, allowed_origins=("https://app.example",))
    assert check_ws_origin("null", config=cfg)[0] is False
    assert check_ws_origin("https://evil.com", config=cfg)[0] is False
    assert check_ws_origin("https://app.example", config=cfg)[0]


def test_ws_disabled_closes():
    app, cfg, _ = _app(ws_enabled=False, push_token="t")
    c = TestClient(app)
    with pytest.raises(Exception):
        with c.websocket_connect("/ux-channel/ws?token=t") as ws:
            ws.receive_json()


def test_ws_connect_unauthorized():
    app, cfg, _ = _app()
    c = TestClient(app)
    with pytest.raises(Exception):
        with c.websocket_connect("/ux-channel/ws") as ws:
            ws.receive_json()


def test_ws_hello_and_public_subscribe():
    app, cfg, _ = _app()
    c = TestClient(app)
    with c.websocket_connect("/ux-channel/ws?topics=public.live") as ws:
        hello = ws.receive_json()
        assert hello["type"] == "hello"
        assert hello.get("v") == "1"
        sub = ws.receive_json()
        assert sub["type"] == "subscribed"
        assert sub["topic"] == "public.live"
        # publish → result
        get_push_bus().publish(
            "public.live", Result.success(morph(target="#x", html="<i>1</i>"))
        )
        # may get ping first if slow — read until result
        for _ in range(5):
            msg = ws.receive_json()
            if msg.get("type") == "result":
                assert msg.get("ok") is True
                assert any(o.get("op") == "morph" for o in msg.get("ops", []))
                break
            if msg.get("type") == "ping":
                continue
        else:
            raise AssertionError("no result message")


def test_ws_private_subscribe_needs_ticket():
    app, cfg, _ = _app()
    c = TestClient(app)
    ticket = sign_push_ticket(cfg, "shop.board")
    with c.websocket_connect(f"/ux-channel/ws?ticket={ticket}") as ws:
        assert ws.receive_json()["type"] == "hello"
        ws.send_json({"type": "subscribe", "topic": "shop.board"})
        msg = ws.receive_json()
        assert msg["type"] == "subscribed"
        ws.send_json({"type": "subscribe", "topic": "other.private"})
        err = ws.receive_json()
        assert err["type"] == "error"
        assert err["code"] == "unauthorized"


def test_ws_token_gates_private():
    app, cfg, _ = _app(push_token="shared-ws")
    c = TestClient(app)
    with c.websocket_connect("/ux-channel/ws?token=shared-ws") as ws:
        assert ws.receive_json()["type"] == "hello"
        ws.send_json({"type": "subscribe", "topic": "x.y"})
        assert ws.receive_json()["type"] == "subscribed"


def test_ws_ping_pong():
    app, cfg, _ = _app()
    c = TestClient(app)
    with c.websocket_connect("/ux-channel/ws?topics=public.x") as ws:
        ws.receive_json()  # hello
        ws.receive_json()  # subscribed
        ws.send_json({"type": "ping"})
        assert ws.receive_json()["type"] == "pong"


def test_ws_intent_with_cap():
    app, cfg, reg = _app()
    cap = reg.sign("Ping.hi", {"n": 1})
    c = TestClient(app)
    with c.websocket_connect("/ux-channel/ws?topics=public.x") as ws:
        ws.receive_json()
        ws.receive_json()
        ws.send_json(
            {
                "type": "intent",
                "action": "Ping.hi",
                "args": {"n": 1},
                "cap": cap,
            }
        )
        # drain until result
        for _ in range(6):
            msg = ws.receive_json()
            if msg.get("type") == "result":
                assert msg.get("ok") is True
                break
            if msg.get("type") in ("ping", "subscribed", "hello"):
                continue
        else:
            raise AssertionError("no intent result")


def test_ws_intent_disabled():
    app, cfg, reg = _app(ws_allow_actions=False)
    cap = reg.sign("Ping.hi", {})
    c = TestClient(app)
    with c.websocket_connect("/ux-channel/ws?topics=public.x") as ws:
        ws.receive_json()
        ws.receive_json()
        ws.send_json({"type": "intent", "action": "Ping.hi", "args": {}, "cap": cap})
        for _ in range(5):
            msg = ws.receive_json()
            if msg.get("type") == "error":
                assert msg["code"] == "forbidden"
                break
        else:
            raise AssertionError("expected forbidden")


def test_ws_bad_message():
    app, cfg, _ = _app()
    c = TestClient(app)
    with c.websocket_connect("/ux-channel/ws?topics=public.x") as ws:
        ws.receive_json()
        ws.receive_json()
        ws.send_text("not-json")
        err = ws.receive_json()
        assert err["type"] == "error"
        assert err["code"] == "bad_message"


def test_channel_sign_ws_alias():
    ch = Channel.boot(
        config=ChannelConfig.production(secret=PROD_SECRET, allow_memory_stores=True)
    )
    t = ch.sign_ws("shop.z", sub="u1")
    assert authorize_ws_subscribe(ch.config, "shop.z", ticket=t)[0]


def test_body_attr_ws():
    ch = Channel.boot(
        config=ChannelConfig.production(secret=PROD_SECRET, allow_memory_stores=True)
    )
    s = attr_string(ch.body_attrs(ws=True, push_topic="public.x"))
    assert 'data-channel-ws="/ux-channel/ws"' in s
    assert "data-channel-push-topic" in s


def test_js_has_subscribe_ws():
    from pathlib import Path

    js = (Path(__file__).resolve().parents[2] / "src/ux_channel/static/ux-channel.js").read_text()
    assert "subscribeWs" in js
    assert "data-channel-ws" in js


def test_development_ws_open_without_token():
    cfg = ChannelConfig.development(secret=DEV_SECRET)
    assert authorize_ws_connect(cfg)[0] is True
