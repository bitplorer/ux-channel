"""1.6.0 improvements: version endpoint, client skew, request id, info."""

import secrets

from fastapi import FastAPI
from fastapi.testclient import TestClient

from ux_channel import ActionRegistry, Result, toast
from ux_channel.asgi.fastapi import mount_channel
from ux_channel.host.config import ChannelConfig
from ux_channel.devtools.info import package_info
from ux_channel.transport.middleware import RequestIdMiddleware, check_client_version


def test_package_info():
    reg = ActionRegistry(secret="test-secret-key-32chars-minimum!!", require_cap=False)

    @reg.action("A")
    def a():
        return Result.success(toast("a"))

    info = package_info(reg)
    assert info["package"] == "ux-channel"
    assert info["actions_count"] == 1
    assert info["protocol"] == "1"


def test_version_and_ready_endpoints():
    cfg = ChannelConfig.development(
        secret="test-secret-key-32chars-minimum!!",
        rate_limit_per_minute=0,
        enforce_same_origin=False,
    )
    app = FastAPI()
    reg = ActionRegistry.from_config(cfg)
    mount_channel(app, reg, config=cfg)
    c = TestClient(app)
    v = c.get("/ux-channel/version").json()
    assert v["version"]
    assert v["v"] == "1"
    r = c.get("/ux-channel/ready").json()
    assert r["ok"] is True
    assert "actions_count" in r


def test_client_version_gate():
    sec = secrets.token_urlsafe(48)
    cfg = ChannelConfig.production(
        sec,
        enforce_same_origin=False,
        rate_limit_per_minute=0,
        require_channel_header=True,
        min_client_version="1.5.0",
        health_list_actions=False,
    )
    app = FastAPI()
    reg = ActionRegistry.from_config(cfg)

    @reg.action("Ping")
    def ping():
        return Result.success(toast("p"))

    mount_channel(app, reg, config=cfg)
    c = TestClient(app)
    cap = reg.mint("Ping", {})
    old = c.post(
        "/ux-channel/action",
        json={"v": "1", "action": "Ping", "args": {}, "cap": cap},
        headers={"X-Channel": "1", "X-Channel-Client-Version": "1.0.0"},
    )
    assert old.status_code == 426
    ok = c.post(
        "/ux-channel/action",
        json={"v": "1", "action": "Ping", "args": {}, "cap": cap},
        headers={"X-Channel": "1", "X-Channel-Client-Version": "1.6.0"},
    )
    assert ok.status_code == 200


def test_check_client_version_helper():
    assert check_client_version(None) is None
    assert check_client_version("1.4.0", min_version="1.5.0")
    assert check_client_version("1.5.0", min_version="1.5.0") is None


def test_request_id_middleware():
    app = FastAPI()
    app.add_middleware(RequestIdMiddleware)

    @app.get("/t")
    def t():
        return {"ok": True}

    c = TestClient(app)
    res = c.get("/t")
    assert res.headers.get("x-request-id")
    res2 = c.get("/t", headers={"X-Request-Id": "custom-id-1"})
    assert res2.headers.get("x-request-id") == "custom-id-1"
