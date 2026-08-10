"""Production readiness: config, rate limit, timeout, security helpers."""

import asyncio
import secrets

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from ux_channel import ActionRegistry, Result, toast
from ux_channel.config import ChannelConfig
from ux_channel.ratelimit import MemoryRateLimiter, rate_limit_hook
from ux_channel.security import content_length_ok, origin_allowed
from ux_channel.types import Intent


def test_production_rejects_weak_secret():
    with pytest.raises(ValueError):
        ChannelConfig.production("short")


def test_production_config_ok():
    sec = secrets.token_urlsafe(48)
    cfg = ChannelConfig.production(sec)
    assert cfg.expose_internal_errors is False
    assert cfg.require_cap is True


def test_from_config_installs_hooks():
    sec = secrets.token_urlsafe(48)
    cfg = ChannelConfig.production(sec, rate_limit_per_minute=1000, rate_limit_burst=100)
    reg = ActionRegistry.from_config(cfg)

    @reg.action("ping")
    def ping():
        return Result.success(toast("ok"))

    cap = reg.sign("ping", {})
    r = reg.dispatch(Intent(action="ping", args={}, cap=cap))
    assert r.ok


def test_rate_limiter():
    lim = MemoryRateLimiter(rate_per_minute=60, burst=2)
    assert lim.allow("a")
    assert lim.allow("a")
    assert not lim.allow("a")


def test_rate_limit_hook():
    lim = MemoryRateLimiter(rate_per_minute=60, burst=1)
    hook = rate_limit_hook(lim)
    reg = ActionRegistry(secret="test-secret-key-32chars-minimum!!", require_cap=False)
    reg.before(hook)

    @reg.action("x")
    def x():
        return Result.success(toast("1"))

    assert reg.dispatch(Intent(action="x")).ok
    r2 = reg.dispatch(Intent(action="x"))
    assert not r2.ok
    assert r2.error.code == "rate_limited"
    assert r2.error.retryable is True


@pytest.mark.asyncio
async def test_action_timeout():
    reg = ActionRegistry(
        secret="test-secret-key-32chars-minimum!!",
        require_cap=False,
        action_timeout_s=0.05,
    )

    @reg.action("slow")
    async def slow():
        await asyncio.sleep(1.0)
        return Result.success(toast("nope"))

    r = await reg.dispatch_async(Intent(action="slow"))
    assert not r.ok
    assert r.error.code == "timeout"


def test_origin_allowed():
    assert origin_allowed(None, allowed_origins=(), enforce_same_origin=True)
    assert origin_allowed(
        "http://localhost:8080",
        allowed_origins=(),
        enforce_same_origin=True,
        request_host="localhost:8080",
    )
    assert not origin_allowed(
        "http://evil.com",
        allowed_origins=(),
        enforce_same_origin=True,
        request_host="localhost:8080",
    )
    assert origin_allowed(
        "https://app.example.com",
        allowed_origins=("https://app.example.com",),
        enforce_same_origin=False,
    )


def test_content_length():
    assert content_length_ok("100", 1000)
    assert not content_length_ok("99999", 1000)


@pytest.mark.asyncio
async def test_dispatch_from_async_raises():
    reg = ActionRegistry(secret="test-secret-key-32chars-minimum!!", require_cap=False)

    @reg.action("t")
    def t():
        return Result.success()

    with pytest.raises(RuntimeError, match="dispatch_async"):
        reg.dispatch(Intent(action="t"))


def test_fastapi_production_mount():
    sec = secrets.token_urlsafe(48)
    cfg = ChannelConfig.production(
        sec,
        health_list_actions=False,
        rate_limit_per_minute=600,
        rate_limit_burst=100,
        enforce_same_origin=False,
        require_channel_header=True,
    )
    app = FastAPI()
    reg = ActionRegistry.from_config(cfg)

    @reg.action("ping")
    def ping():
        return Result.success(toast("p"))

    from ux_channel.asgi.fastapi import mount_channel

    mount_channel(app, reg, config=cfg)
    client = TestClient(app)
    h = client.get("/ux-channel/health")
    assert h.status_code == 200
    assert "actions" not in h.json()
    rdy = client.get("/ux-channel/ready")
    assert rdy.status_code == 200
    cap = reg.sign("ping", {})
    res = client.post(
        "/ux-channel/action",
        json={"v": "1", "action": "ping", "args": {}, "cap": cap},
        headers={"Accept": "application/uid+json", "X-Channel": "1"},
    )
    assert res.status_code == 200
