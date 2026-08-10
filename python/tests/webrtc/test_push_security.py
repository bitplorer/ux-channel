"""Production SSE push authorization — unit + HTTP."""

from __future__ import annotations

import asyncio

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from ux_channel import Channel, ChannelConfig, Result, morph
from ux_channel.render.kit import attr_string, demo_button, demo_page, demo_scripts, script_tags
from ux_channel.asgi.fastapi import mount_channel
from ux_channel.transport.push import PushBus, get_push_bus
from ux_channel.security.push_security import (
    PushAuthError,
    authorize_push_subscribe,
    sign_push_ticket,
    validate_topic,
    verify_push_ticket,
)
from ux_channel.host.registry import ActionRegistry

PROD_SECRET = "prod-secret-key-32chars-minimum!!!!"
DEV_SECRET = "dev-secret-key-32chars-minimum!!!!"


def _prod_app(**kwargs):
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
    mount_channel(app, reg, config=cfg)
    return app, cfg


def test_validate_topic_rejects_path_and_empty():
    with pytest.raises(PushAuthError):
        validate_topic("")
    with pytest.raises(PushAuthError):
        validate_topic("../etc")
    with pytest.raises(PushAuthError):
        validate_topic("a/b")
    with pytest.raises(PushAuthError):
        validate_topic("bad topic")
    assert validate_topic("public.rates") == "public.rates"
    assert validate_topic("shop:lobby-1") == "shop:lobby-1"


def test_production_denies_private_without_creds():
    cfg = ChannelConfig.production(secret=PROD_SECRET)
    ok, reason = authorize_push_subscribe(cfg, "private.x")
    assert ok is False
    assert "required" in reason or "authorization" in reason


def test_production_allows_public_prefix():
    cfg = ChannelConfig.production(secret=PROD_SECRET)
    ok, reason = authorize_push_subscribe(cfg, "public.board")
    assert ok is True
    assert reason == "public"


def test_custom_public_prefix():
    cfg = ChannelConfig.production(
        secret=PROD_SECRET,
        push_public_prefixes=("open.", "public."),
    )
    assert authorize_push_subscribe(cfg, "open.ticker")[0] is True
    assert authorize_push_subscribe(cfg, "secret.x")[0] is False


def test_public_disabled_requires_creds():
    cfg = ChannelConfig.production(
        secret=PROD_SECRET,
        push_allow_public=False,
        push_token="shared-push-token-value",
    )
    assert authorize_push_subscribe(cfg, "public.x")[0] is False
    assert authorize_push_subscribe(cfg, "public.x", token="shared-push-token-value")[0]


def test_ticket_roundtrip_and_mismatch():
    cfg = ChannelConfig.production(secret=PROD_SECRET)
    ticket = sign_push_ticket(cfg, "shop.a", sub="user-1")
    data = verify_push_ticket(cfg, ticket, "shop.a")
    assert data["topic"] == "shop.a"
    with pytest.raises(PushAuthError):
        verify_push_ticket(cfg, ticket, "shop.b")
    with pytest.raises(PushAuthError):
        verify_push_ticket(cfg, ticket, "shop.a", expected_sub="other")
    ok, _ = authorize_push_subscribe(cfg, "shop.a", ticket=ticket)
    assert ok


def test_ticket_bad_signature():
    cfg = ChannelConfig.production(secret=PROD_SECRET)
    ticket = sign_push_ticket(cfg, "t.x")
    with pytest.raises(PushAuthError):
        verify_push_ticket(cfg, ticket + "x", "t.x")
    other = ChannelConfig.production(secret="other-secret-key-32chars-minimum!!!")
    with pytest.raises(PushAuthError):
        verify_push_ticket(other, ticket, "t.x")


def test_push_token_bearer_and_query():
    cfg = ChannelConfig.production(secret=PROD_SECRET, push_token="tok-abc")
    assert authorize_push_subscribe(cfg, "x", token="tok-abc")[0]
    assert authorize_push_subscribe(cfg, "x", bearer="tok-abc")[0]
    assert authorize_push_subscribe(cfg, "x", token="wrong")[0] is False


def test_development_open_without_auth():
    cfg = ChannelConfig.development(secret=DEV_SECRET)
    assert cfg.push_require_auth is False
    assert authorize_push_subscribe(cfg, "any.topic")[0] is True


def test_production_rejects_push_open():
    with pytest.raises(ValueError, match="push_open"):
        ChannelConfig.production(secret=PROD_SECRET, push_open=True)


def test_channel_sign_push():
    ch = Channel.boot(
        config=ChannelConfig.production(secret=PROD_SECRET, allow_memory_stores=True)
    )
    t = ch.sign_push("orders.live", sub="u9")
    ok, reason = authorize_push_subscribe(ch.config, "orders.live", ticket=t)
    assert ok and reason == "ticket"


def test_http_private_denied():
    app, _ = _prod_app()
    c = TestClient(app)
    r = c.get("/ux-channel/push/private.board")
    assert r.status_code == 401
    assert r.json()["ok"] is False


def test_http_bad_token_denied():
    app, _ = _prod_app(push_token="good-token")
    c = TestClient(app)
    r = c.get("/ux-channel/push/shop.x", params={"token": "bad"})
    assert r.status_code == 401


def test_http_auth_matrix_matches_authorize():
    """HTTP 401 path + authorize matrix for 200 cases (avoid long-lived SSE in TestClient)."""
    app, cfg = _prod_app(push_token="push-shared-secret")
    c = TestClient(app)
    # denied paths return JSON immediately
    assert c.get("/ux-channel/push/shop.board").status_code == 401
    assert c.get("/ux-channel/push/shop.board", params={"token": "nope"}).status_code == 401
    ticket = sign_push_ticket(cfg, "shop.board")
    assert c.get("/ux-channel/push/other", params={"ticket": ticket}).status_code == 401
    # allowed combinations (unit) — same gates the route uses
    assert authorize_push_subscribe(cfg, "public.rates")[0]
    assert authorize_push_subscribe(cfg, "shop.board", token="push-shared-secret")[0]
    assert authorize_push_subscribe(cfg, "shop.board", bearer="push-shared-secret")[0]
    assert authorize_push_subscribe(cfg, "shop.board", ticket=ticket)[0]


def test_push_bus_publish_delivers_to_queue():
    bus = PushBus()
    q: asyncio.Queue = asyncio.Queue(maxsize=8)
    bus.subscribe("public.live", q)
    bus.publish("public.live", Result.success(morph(target="#x", html="<b>1</b>")))
    item = q.get_nowait()
    assert item.get("ok") is True
    assert any(o.get("op") == "morph" for o in item.get("ops", []))


def test_body_attr_push_ticket():
    ch = Channel.boot(
        config=ChannelConfig.production(secret=PROD_SECRET, allow_memory_stores=True)
    )
    ticket = ch.sign_push("public.x")
    s = attr_string(ch.body_attrs(push_topic="public.x", push_ticket=ticket))
    assert "data-channel-push-ticket=" in s
    assert 'data-channel-push-topic="public.x"' in s


def test_js_client_mentions_ticket():
    from pathlib import Path

    js = (Path(__file__).resolve().parents[2] / "src/ux_channel/static/ux-channel.js").read_text()
    assert "PUSH_TICKET_ATTR" in js or "data-channel-push-ticket" in js
    assert "ticket=" in js
