"""Wireshark-like tracing for actions and bridges."""

import secrets

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from ux_channel import ActionRegistry, Result, morph, toast
from ux_channel.bridge_api import mount_ops
from ux_channel.config import ChannelConfig
from ux_channel.trace import (
    FrameKind,
    TraceConfig,
    enable_tracing,
    get_tracer,
    set_tracer,
    ChannelTracer,
)
from ux_channel.types import Intent


@pytest.fixture
def tracer():
    t = ChannelTracer(TraceConfig(enabled=True, retain=100, capture_payloads=True))
    set_tracer(t)
    yield t
    set_tracer(ChannelTracer(TraceConfig(enabled=False)))


def test_trace_dispatch_pipeline(tracer):
    reg = ActionRegistry(secret="test-secret-key-32chars-minimum!!", require_cap=True)

    @reg.action("Demo.run")
    def run(n: int = 1):
        return Result.success(
            morph(target="#x", html=f'<div id="x">{n}</div>'),
            toast("hi"),
            *mount_ops("c1", "sparkline", props={"values": [1, 2]}),
        )

    cap = reg.mint("Demo.run", {"n": 2})
    r = reg.dispatch(
        Intent(action="Demo.run", args={"n": 2}, cap=cap, request_id="req_test1")
    )
    assert r.ok
    kinds = [f.kind for f in tracer.frames(request_id="req_test1")]
    assert FrameKind.INTENT_IN.value in kinds
    assert FrameKind.CAP_OK.value in kinds
    assert FrameKind.RESULT_OUT.value in kinds
    assert FrameKind.BRIDGE.value in kinds or any(k == "bridge" for k in kinds)
    assert any(k == FrameKind.OP.value or k == "op" for k in kinds)
    conv = tracer.conversations()
    assert any(c["request_id"] == "req_test1" for c in conv)


def test_trace_cap_fail(tracer):
    reg = ActionRegistry(secret="test-secret-key-32chars-minimum!!", require_cap=True)

    @reg.action("X")
    def x():
        return Result.success()

    r = reg.dispatch(Intent(action="X", args={}, request_id="req_bad"))
    assert not r.ok
    kinds = [f.kind for f in tracer.frames(request_id="req_bad")]
    assert FrameKind.CAP_FAIL.value in kinds


def test_export_json(tracer):
    tracer.emit("custom", "hello", request_id="r", detail={"password": "secret"})
    raw = tracer.export_json()
    assert "hello" in raw
    assert "secret" not in raw  # redacted
    assert "***" in raw


def test_trace_http_api():
    sec = secrets.token_urlsafe(48)
    cfg = ChannelConfig.development(
        secret=sec,
        trace_enabled=True,
        trace_http=True,
        enforce_same_origin=False,
        rate_limit_per_minute=0,
    )
    enable_tracing()
    app = FastAPI()
    reg = ActionRegistry.from_config(cfg)

    @reg.action("P")
    def p():
        return Result.success(toast("x"))

    from ux_channel.asgi.fastapi import mount_channel

    mount_channel(app, reg, config=cfg)
    client = TestClient(app)
    cap = reg.mint("P", {})
    client.post(
        "/ux-channel/action",
        json={"v": "1", "action": "P", "args": {}, "cap": cap, "request_id": "req_http"},
    )
    dump = client.get("/ux-channel/trace")
    assert dump.status_code == 200
    body = dump.json()
    assert body["enabled"] is True
    assert body["count"] >= 1
    conv = client.get("/ux-channel/trace/conversations")
    assert conv.status_code == 200
    # client ingest
    ing = client.post(
        "/ux-channel/trace/client",
        json={
            "frames": [
                {
                    "kind": "client.op",
                    "summary": "apply morph",
                    "request_id": "req_http",
                    "action": "P",
                }
            ]
        },
    )
    assert ing.status_code == 200
    assert ing.json()["ok"] is True


def test_static_inspector_js():
    from ux_channel.asgi.fastapi import mount_channel
    from ux_channel.config import ChannelConfig

    app = FastAPI()
    reg = ActionRegistry(secret="test-secret-key-32chars-minimum!!")
    cfg = ChannelConfig.development(
        secret="test-secret-key-32chars-minimum!!",
        enforce_same_origin=False,
        rate_limit_per_minute=0,
    )
    mount_channel(app, reg, config=cfg)
    c = TestClient(app)
    r = c.get("/ux-channel/static/ux-inspector.js")
    assert r.status_code == 200
    assert "uidInspector" in r.text
