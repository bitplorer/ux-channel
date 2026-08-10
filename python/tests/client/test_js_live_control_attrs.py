"""Live-JS safety: control attrs must survive HTML attribute embedding."""

from __future__ import annotations

import json
import re
from html import unescape

from fastapi import FastAPI
from fastapi.testclient import TestClient

from ux_channel import Channel, ChannelConfig


SECRET = "js-live-control-attrs-secret-key-32!"


def test_str_control_preserves_args_through_html_parse():
    app = FastAPI()
    ch = Channel.boot(
        app,
        config=ChannelConfig.development(
            secret=SECRET,
            allow_memory_stores=True,
            require_cap=True,
            require_channel_header=True,
            rate_limit_per_minute=0,
        ),
    )

    @ch.on
    def bump(sku: str = "") -> object:
        return ch.done(notice=sku)

    ctrl = ch.control(bump, trust_sku="X")
    html = f"<button {ctrl}></button>"
    assert "data-channel-args=" in html
    # entity-escaped quotes from attr_escape
    assert "quot" in html
    m = re.search(r'data-channel-args="([^"]*)"', html)
    assert m, html
    args = json.loads(unescape(m.group(1)))
    assert args.get("sku") == "X"

    client = TestClient(app)
    cap = re.search(r'data-channel-cap="([^"]*)"', html).group(1)
    r = client.post(
        "/ux-channel/action",
        json={"v": "1", "action": "bump", "args": args, "cap": cap},
        headers={"X-Channel": "1", "X-Channel-Client-Version": "0.1.0"},
    )
    assert r.status_code == 200, r.text
    assert r.json().get("ok") is True


def test_unsafe_as_dict_join_breaks_args_attr():
    # Footgun: joining as_dict() into HTML truncates JSON args at first quote.
    app = FastAPI()
    ch = Channel.boot(
        app,
        config=ChannelConfig.development(
            secret=SECRET, allow_memory_stores=True, require_cap=True
        ),
    )

    @ch.on
    def bump(sku: str = "") -> object:
        return ch.done()

    d = ch.control(bump, trust_sku="X").as_dict()
    broken = " ".join("%s=\"%s\"" % (k, v) for k, v in d.items())
    assert "data-channel-args=\"{ " in broken or 'data-channel-args="{' in broken
    m = re.search(r'data-channel-args="([^"]*)"', broken)
    assert m is not None
    assert m.group(1) == "{"
