"""UxDom paint stays free of CSRF; wire uses host_csrf + channel header."""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from ux_channel import Channel, ChannelConfig
from ux_channel.security.host_csrf import intent_headers
from ux_channel.security.security import channel_header_ok
from ux_channel_ux_dom.csrf import (
    CHANNEL_CSRF_HEADER,
    assert_csrf_names_do_not_collide,
    channel_and_ux_dom_headers,
    ux_dom_csrf_meta,
)

SECRET = "ux_dom-csrf-coexist-secret-key-32b!!"


def test_no_name_collision():
    assert_csrf_names_do_not_collide()


def test_host_token_alone_not_enough():
    assert channel_header_ok({"X-CSRFToken": "abc"}, required=True) is False
    assert channel_header_ok({"X-Custom-CSRF": "x", "X-Channel": "1"}, required=True)


def test_headers_helpers():
    h = channel_and_ux_dom_headers(host_token="t")
    assert h[CHANNEL_CSRF_HEADER] == "1"
    h2 = intent_headers(host_token="t", forward_as=("X-Only",), extra={"X-Channel": "0"})
    assert h2[CHANNEL_CSRF_HEADER] == "1" and h2["X-Only"] == "t"


def test_meta_helper():
    assert "X-CSRF-TOKEN" in ux_dom_csrf_meta("x")


def test_http_ok():
    app = FastAPI()
    ch = Channel.boot(
        app,
        config=ChannelConfig.development(
            secret=SECRET,
            allow_memory_stores=True,
            require_channel_header=True,
            require_cap=True,
            rate_limit_per_minute=0,
        ),
    )

    @ch.on
    def ping():
        return ch.done()

    client = TestClient(app)
    cap = ch.control("ping").as_dict()["data-channel-cap"]
    assert (
        client.post(
            "/ux-channel/action",
            json={"v": "1", "action": "ping", "args": {}, "cap": cap},
            headers=intent_headers(host_token="z"),
        ).status_code
        == 200
    )


def test_js_and_paint():
    js = Path("src/ux_channel/static/ux-channel.js").read_text()
    assert "buildIntentHeaders" in js
    from ux_channel_ux_dom import control_ux_dom

    app = FastAPI()
    ch = Channel.boot(
        app,
        config=ChannelConfig.development(
            secret=SECRET, allow_memory_stores=True, require_cap=True
        ),
    )

    @ch.on
    def add():
        return ch.done()

    u = control_ux_dom(ch, "add")
    assert "data_channel_cap" in u and not any("csrf" in k.lower() for k in u)
