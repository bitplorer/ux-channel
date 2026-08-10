"""Production path: HTTP security events + WS resubscribe client contract."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from ux_channel import Channel, ChannelConfig
from ux_channel.security_events import SecurityEventBus, get_security_bus, set_security_bus


def test_http_origin_deny_emits_event():
    set_security_bus(SecurityEventBus(retain=50))
    get_security_bus().clear()
    app = FastAPI()
    cfg = ChannelConfig.production(
        "s" * 32,
        allow_memory_stores=True,
        require_channel_header=True,
        enforce_same_origin=True,
        allowed_origins=("https://good.example",),
    )
    ch = Channel.boot(app, config=cfg)

    @ch.on(name="P.hi")
    def hi():
        return ch.done()

    client = TestClient(app)
    cap = ch.registry.sign("P.hi", {})
    res = client.post(
        "/ux-channel/action",
        json={"v": "1", "action": "P.hi", "args": {}, "cap": cap},
        headers={
            "Origin": "https://evil.example",
            "X-Channel": "1",
            "Content-Type": "application/json",
        },
    )
    assert res.status_code == 403
    ev = get_security_bus().recent(10, kind="http_origin_deny")
    assert ev, "expected http_origin_deny security event"


def test_http_csrf_header_deny_emits_event():
    set_security_bus(SecurityEventBus(retain=50))
    get_security_bus().clear()
    app = FastAPI()
    cfg = ChannelConfig.production(
        "s" * 32,
        allow_memory_stores=True,
        require_channel_header=True,
        enforce_same_origin=False,
    )
    ch = Channel.boot(app, config=cfg)

    @ch.on(name="P.hi2")
    def hi():
        return ch.done()

    client = TestClient(app)
    cap = ch.registry.sign("P.hi2", {})
    res = client.post(
        "/ux-channel/action",
        json={"v": "1", "action": "P.hi2", "args": {}, "cap": cap},
        headers={"Content-Type": "application/json"},  # no X-Channel
    )
    assert res.status_code == 403
    ev = get_security_bus().recent(10, kind="http_csrf_deny")
    assert ev


def test_client_js_ws_resubscribe_contract():
    from pathlib import Path
    js = Path("src/ux_channel/static/ux-channel.js").read_text()
    assert "wsTopics" in js
    assert "lastWsBaseUrl" in js
    assert "_rememberTopics" in js
    assert "_reconnect" in js
    # on open resubscribes
    assert 'type: "subscribe"' in js or "type: \"subscribe\"" in js
    assert "wsReconnectAttempt" in js
