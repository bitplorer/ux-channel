"""Next-step features: trace auth, codegen, html_safe, starlette parity, e2e smoke."""

import secrets

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.applications import Starlette
from starlette.testclient import TestClient as StarletteClient

from ux_channel import ActionRegistry, Result, toast
from ux_channel.codegen import generate_ts_client
from ux_channel.config import ChannelConfig
from ux_channel.html_safe import esc, user_content
from ux_channel.types import Intent


def test_html_safe():
    assert "<" not in esc("<script>")
    assert "<" in user_content("<x>")


def test_codegen_ts():
    reg = ActionRegistry(secret="test-secret-key-32chars-minimum!!", require_cap=False)

    @reg.action("Orders.place")
    def place():
        return Result.success(toast("ok"))

    src = generate_ts_client(reg)
    assert "Orders.place" in src
    assert "UidActionName" in src
    assert "runUidAction" in src


def test_trace_requires_token_in_production():
    sec = secrets.token_urlsafe(48)
    cfg = ChannelConfig.production(
        sec,
        enforce_same_origin=False,
        rate_limit_per_minute=0,
        trace_enabled=True,
        trace_http=True,
        trace_token="secret-trace",
        health_list_actions=False,
        require_channel_header=False,
    )
    # production() may warn on trace payloads - ok
    app = FastAPI()
    reg = ActionRegistry.from_config(cfg)

    @reg.action("P")
    def p():
        return Result.success(toast("x"))

    from ux_channel.asgi.fastapi import mount_channel

    mount_channel(app, reg, config=cfg)
    client = TestClient(app)
    denied = client.get("/ux-channel/trace")
    assert denied.status_code == 401
    ok = client.get("/ux-channel/trace", headers={"Authorization": "Bearer secret-trace"})
    assert ok.status_code == 200


def test_trace_denied_production_without_token():
    sec = secrets.token_urlsafe(48)
    cfg = ChannelConfig.production(
        sec,
        enforce_same_origin=False,
        rate_limit_per_minute=0,
        trace_enabled=True,
        trace_http=True,
        trace_token=None,
        health_list_actions=False,
        require_channel_header=False,
    )
    app = FastAPI()
    reg = ActionRegistry.from_config(cfg)
    from ux_channel.asgi.fastapi import mount_channel

    mount_channel(app, reg, config=cfg)
    client = TestClient(app)
    assert client.get("/ux-channel/trace").status_code == 401


def test_starlette_action_parity():
    from ux_channel.asgi.starlette import mount_channel_starlette

    reg = ActionRegistry(secret="test-secret-key-32chars-minimum!!", require_cap=True)

    @reg.action("Hi")
    def hi():
        return Result.success(toast("hi"))

    cfg = ChannelConfig.development(
        secret="test-secret-key-32chars-minimum!!",
        enforce_same_origin=False,
        rate_limit_per_minute=0,
    )
    app = Starlette()
    mount_channel_starlette(app, reg, config=cfg)
    client = StarletteClient(app)
    cap = reg.sign("Hi", {})
    res = client.post(
        "/ux-channel/action",
        json={"v": "1", "action": "Hi", "args": {}, "cap": cap},
        headers={"Accept": "application/uid+json", "X-Channel": "1"},
    )
    assert res.status_code == 200
    assert res.json()["ok"] is True
    assert client.get("/ux-channel/ready").status_code == 200


def test_e2e_smoke_counter_flow():
    """HTTP-level e2e: health → action morph → static assets."""
    from ux_channel.asgi.fastapi import mount_channel
    from ux_channel.html import action_attrs

    cfg = ChannelConfig.development(
        secret="test-secret-key-32chars-minimum!!",
        enforce_same_origin=False,
        rate_limit_per_minute=0,
        trace_http=True,
    )
    app = FastAPI()
    reg = ActionRegistry.from_config(cfg)

    def html(n: int) -> str:
        return f'<div data-channel-id="c"><span>{n}</span></div>'

    @reg.action("Counter.inc")
    def inc(n: int = 0):
        from ux_channel import morph

        return Result.success(morph(target='[data-channel-id="c"]', html=html(n + 1)))

    mount_channel(app, reg, config=cfg)

    @app.get("/")
    def index():
        from fastapi.responses import HTMLResponse

        return HTMLResponse(
            f"<html><body data-channel-endpoint='/ux-channel/action'>{html(0)}</body></html>"
        )

    c = TestClient(app)
    assert c.get("/ux-channel/health").json()["ok"] is True
    assert c.get("/ux-channel/ready").json()["status"] == "ready"
    js = c.get("/ux-channel/static/ux-channel.js")
    assert js.status_code == 200 and "uxChannel" in js.text
    assert c.get("/ux-channel/static/ux-channel.min.js").status_code == 200
    cap = reg.sign("Counter.inc", {"n": 0})
    r = c.post(
        "/ux-channel/action",
        json={"v": "1", "action": "Counter.inc", "args": {"n": 0}, "cap": cap},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] and "1" in body["ops"][0]["html"]
    assert body["meta"].get("runtime")
    # second click with new cap
    cap2 = reg.sign("Counter.inc", {"n": 1})
    r2 = c.post(
        "/ux-channel/action",
        json={
            "v": "1",
            "action": "Counter.inc",
            "args": {"n": 1},
            "cap": cap2,
            "idempotency_key": "inc-1",
        },
    )
    assert r2.json()["ops"][0]["html"].find("2") >= 0
