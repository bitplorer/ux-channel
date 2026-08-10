"""Host CSRF is optional and name-agnostic; channel CSRF is only X-Channel."""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from ux_channel import Channel, ChannelConfig
from ux_channel.host_csrf import (
    CHANNEL_CSRF_HEADER,
    CHANNEL_CSRF_VALUE,
    host_csrf_meta,
    intent_headers,
    is_channel_csrf_header,
    looks_like_host_csrf_name,
)
from ux_channel.security import channel_header_ok

SECRET = "host-csrf-agnostic-secret-key-32b!!"


def test_channel_csrf_stable():
    assert CHANNEL_CSRF_HEADER == "X-Channel"
    assert CHANNEL_CSRF_VALUE == "1"
    assert is_channel_csrf_header("X-Channel")
    assert not is_channel_csrf_header("X-CSRFToken")


def test_host_name_heuristic():
    assert looks_like_host_csrf_name("csrfmiddlewaretoken")
    assert looks_like_host_csrf_name("X-My-Custom-CSRF")
    assert looks_like_host_csrf_name("authenticity_token")
    assert not looks_like_host_csrf_name("X-Channel")
    assert not looks_like_host_csrf_name("viewport")


def test_intent_headers_explicit_forward_as():
    h = intent_headers(host_token="sekrit", forward_as=("X-App-AntiForgery",))
    assert h == {
        "X-App-AntiForgery": "sekrit",
        CHANNEL_CSRF_HEADER: "1",
    }


def test_intent_headers_extra_cannot_clear_channel():
    h = intent_headers(extra={"X-Channel": "0", "Authorization": "Bearer x"})
    assert h[CHANNEL_CSRF_HEADER] == "1"
    assert h["Authorization"] == "Bearer x"


def test_host_meta_any_name():
    assert 'name="my-framework-csrf"' in host_csrf_meta("t", name="my-framework-csrf")


def test_server_only_channel_header():
    assert channel_header_ok({"X-App-AntiForgery": "x"}, required=True) is False
    assert (
        channel_header_ok(
            {"X-App-AntiForgery": "x", "X-Channel": "1"}, required=True
        )
        is True
    )


def test_http_arbitrary_host_header():
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
    r = client.post(
        "/ux-channel/action",
        json={"v": "1", "action": "ping", "args": {}, "cap": cap},
        headers=intent_headers(
            host_token="abc", forward_as=("X-Starlette-CSRF",)
        ),
    )
    assert r.status_code == 200


def test_js_clean_builder():
    js = Path("src/ux_channel/static/ux-channel.js").read_text()
    assert "function buildIntentHeaders" in js
    assert "__UX_CHANNEL_CSRF__" in js
    assert 'headers["X-Channel"] = "1"' in js
    # not fixated on a single meta selector string
    assert "isHostCsrfName" in js
