"""Wave A/B/C integration tests."""

import secrets

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from ux_channel.push import get_push_bus
from ux_channel import (
    ActionContext,
    ActionRegistry,
    MemoryIdempotencyStore,
    MemoryNonceStore,
    Principal,
    Result,
    morph,
    toast,
)
from ux_channel.capability import CapService
from ux_channel.config import ChannelConfig
from ux_channel.context import Principal as P
from ux_channel.types import Intent


def test_principal_bound_cap():
    secret = "test-secret-key-32chars-minimum!!"
    caps = CapService(secret)
    tok = caps.mint("A", {}, sub="user-1", scopes=["read"])
    data = caps.verify(tok, "A", {}, expected_sub="user-1", required_scopes=["read"])
    assert data["sub"] == "user-1"
    with pytest.raises(Exception):
        caps.verify(tok, "A", {}, expected_sub="user-2")


def test_nonce_once_cap():
    secret = "test-secret-key-32chars-minimum!!"
    store = MemoryNonceStore()
    reg = ActionRegistry(secret=secret, require_cap=True, nonce_store=store)

    @reg.action("Once")
    def once():
        return Result.success(toast("ok"))

    cap = reg.mint("Once", {}, once=True)
    # extract jti via verify
    data = reg._caps.verify(cap, "Once", {})
    assert data.get("jti")
    r1 = reg.dispatch(Intent(action="Once", args={}, cap=cap, request_id="r1"))
    assert r1.ok
    r2 = reg.dispatch(Intent(action="Once", args={}, cap=cap, request_id="r2"))
    assert not r2.ok
    assert "replay" in (r2.error.message if r2.error else "")


def test_idempotency_store():
    store = MemoryIdempotencyStore()
    reg = ActionRegistry(
        secret="test-secret-key-32chars-minimum!!",
        require_cap=False,
        idempotency_store=store,
    )
    n = {"c": 0}

    @reg.action("Inc")
    def inc():
        n["c"] += 1
        return Result.success(toast(str(n["c"])))

    r1 = reg.dispatch(Intent(action="Inc", idempotency_key="k1"))
    r2 = reg.dispatch(Intent(action="Inc", idempotency_key="k1"))
    assert r1.ok and r2.ok
    assert n["c"] == 1  # second was cache hit
    assert r1.ops[0]["message"] == r2.ops[0]["message"]


def test_action_context_injection():
    reg = ActionRegistry(secret="test-secret-key-32chars-minimum!!", require_cap=False)
    reg.auth_resolver = lambda req: Principal(id="u1", scopes=("x",))

    @reg.action("Who")
    def who(ctx: ActionContext):
        assert ctx.principal and ctx.principal.id == "u1"
        return Result.success(toast(ctx.principal.id))

    r = reg.dispatch(Intent(action="Who"))
    assert r.ok
    assert r.ops[0]["message"] == "u1"


def test_file_actions():
    from ux_channel.actions_file import action, load_actions_from_package
    import types, sys

    mod = types.ModuleType("ux_channel_test_actions")

    @action("Demo.hi")
    def hi():
        return Result.success(toast("hi"))

    mod.hi = hi
    sys.modules["ux_channel_test_actions"] = mod
    reg = ActionRegistry(secret="test-secret-key-32chars-minimum!!", require_cap=False)
    names = load_actions_from_package(reg, "ux_channel_test_actions")
    assert "Demo.hi" in names
    assert reg.dispatch(Intent(action="Demo.hi")).ok


@pytest.mark.asyncio
async def test_push_bus():
    bus = get_push_bus()
    import asyncio
    q = asyncio.Queue()
    bus.subscribe("t1", q)
    n = bus.publish("t1", Result.success(toast("ping")))
    assert n == 1
    item = await q.get()
    assert item["ops"][0]["op"] == "toast"
    bus.unsubscribe("t1", q)


def test_sse_action_endpoint():
    app = FastAPI()
    cfg = ChannelConfig.development(
        secret="test-secret-key-32chars-minimum!!",
        enforce_same_origin=False,
        rate_limit_per_minute=0,
    )
    reg = ActionRegistry.from_config(cfg)

    @reg.action("S")
    def s():
        return Result.success(toast("streamed"))

    from ux_channel.asgi.fastapi import mount_channel

    mount_channel(app, reg, config=cfg)
    client = TestClient(app)
    cap = reg.mint("S", {})
    res = client.post(
        "/ux-channel/action",
        json={"v": "1", "action": "S", "args": {}, "cap": cap, "accept_stream": True},
        headers={"Accept": "text/event-stream"},
    )
    assert res.status_code == 200
    assert "text/event-stream" in res.headers.get("content-type", "")
    assert b"streamed" in res.content or b"toast" in res.content


def test_client_js_version():
    from pathlib import Path
    from ux_channel import __version__ as v
    text = Path("src/ux_channel/static/ux-channel.js").read_text()
    assert f'VERSION = "{v}"' in text or f'VERSION="{v}"' in text


def test_sparkline_adapter_shipped():
    from ux_channel.asgi.fastapi import static_dir

    assert (static_dir() / "adapters" / "sparkline.js").is_file()


def test_metrics_prom():
    from ux_channel.metrics_prom import PrometheusMetrics

    m = PrometheusMetrics()
    m.incr("ux_channel.actions", tags={"ok": "true"})
    m.timing("ux_channel.action_ms", 12.5, action="X")
    text = m.render_prometheus()
    assert "ux_channel_actions" in text
