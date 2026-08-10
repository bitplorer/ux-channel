from fastapi import FastAPI
from fastapi.testclient import TestClient

from ux_channel import ActionRegistry, Result, morph
from ux_channel.asgi.fastapi import mount_channel
from ux_channel.host.config import ChannelConfig
import secrets


def build_app(*, list_actions: bool = True):
    app = FastAPI()
    # development-style registry for tests
    reg = ActionRegistry(secret="test-secret-key-32chars-minimum!!", require_cap=True)

    @reg.action("Counter.inc")
    def inc(n: int = 0) -> Result:
        return Result.success(
            morph(
                target='[data-channel-id="c"]',
                html=f'<div data-channel-id="c">{n + 1}</div>',
            )
        )

    @reg.action("Async.ok")
    async def aok():
        return Result.success(morph(target="#x", html='<div id="x">ok</div>'))

    cfg = ChannelConfig.development(
        secret="test-secret-key-32chars-minimum!!",
        health_list_actions=list_actions,
        enforce_same_origin=False,
        rate_limit_per_minute=0,  # disable IP limit noise in unit tests
    )
    # rebuild with config for health flag only on mount
    mount_channel(app, reg, config=cfg)
    return app, reg


def test_action_endpoint():
    app, reg = build_app()
    client = TestClient(app)
    cap = reg.mint("Counter.inc", {"n": 2})
    res = client.post(
        "/ux-channel/action",
        json={
            "v": "1",
            "action": "Counter.inc",
            "args": {"n": 2},
            "cap": cap,
            "request_id": "r1",
        },
        headers={"Accept": "application/uid+json"},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["ok"] is True
    assert body["ops"][0]["op"] == "morph"
    assert "3" in body["ops"][0]["html"]
    assert body["meta"]["request_id"] == "r1"


def test_health():
    app, _ = build_app(list_actions=True)
    client = TestClient(app)
    r = client.get("/ux-channel/health")
    assert r.status_code == 200
    assert "Counter.inc" in r.json().get("actions", [])


def test_static_js():
    app, _ = build_app()
    client = TestClient(app)
    r = client.get("/ux-channel/static/ux-channel.js")
    assert r.status_code == 200
    assert "uxChannel" in r.text
    r2 = client.get("/ux-channel/static/ux-bridge.js")
    assert r2.status_code == 200


def test_async_action_endpoint():
    app, reg = build_app()
    client = TestClient(app)
    cap = reg.mint("Async.ok", {})
    res = client.post(
        "/ux-channel/action",
        json={"v": "1", "action": "Async.ok", "args": {}, "cap": cap},
    )
    assert res.status_code == 200
    assert res.json()["ok"] is True


def test_html_accept_fallback():
    app, reg = build_app()
    client = TestClient(app)
    cap = reg.mint("Counter.inc", {"n": 0})
    res = client.post(
        "/ux-channel/action",
        json={"v": "1", "action": "Counter.inc", "args": {"n": 0}, "cap": cap},
        headers={"Accept": "text/html"},
    )
    assert res.status_code == 200
    assert "data-channel-id" in res.text
