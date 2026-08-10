"""WebRTC plugin DX — no UI chrome in library."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from ux_channel import Channel, ChannelConfig
from ux_channel.paint.demo import attr_string, demo_button, demo_page, demo_scripts, script_tags
from ux_channel.host.dx import DAY1_WEBRTC_API
from ux_channel.realtime.webrtc import reset_rtc_store


def _boot(**kw):
    reset_rtc_store()
    app = FastAPI()
    base = dict(
        secret="dev-secret-key-32chars-minimum!!!!",
        allow_memory_stores=True,
        webrtc_enabled=True,
        webrtc_require_ticket=False,
    )
    base.update(kw)
    ch = Channel.boot(app, config=ChannelConfig.development(**base))
    return app, ch


def test_day1_plugin_not_page_panel():
    assert "plugin" in DAY1_WEBRTC_API
    assert "session" not in DAY1_WEBRTC_API  # power: ch.webrtc.session(...).plugin()
    assert "page" not in DAY1_WEBRTC_API
    assert "panel" not in DAY1_WEBRTC_API


def test_no_panel_methods_on_plane():
    app, ch = _boot()
    assert not hasattr(ch.webrtc, "page") or not callable(getattr(ch.webrtc, "page", None))
    # page removed
    assert not hasattr(WebRTC := type(ch.webrtc), "page")
    assert not hasattr(type(ch.webrtc), "panel")
    assert hasattr(type(ch.webrtc), "plugin")


def test_plugin_bag_no_panel_html():
    app, ch = _boot()
    p = ch.webrtc.plugin("lobby", sub="u")
    d = p.as_dict()
    assert "panel_html" not in d
    assert "scripts_html" in d and "client" in d and "attrs" in d
    assert "credential" not in p.attr_string
    assert "ux-channel.js" in script_tags(p) or "ux-webrtc" in script_tags(p)


def test_session_ticket():
    app, ch = _boot(webrtc_require_ticket=True)
    p = ch.webrtc.session("r", sub="u1").plugin()
    assert p.ticket
    assert p.client.get("ticket")


def test_example_compiles():
    from examples.webrtc_ready import app as mod
    c = TestClient(mod.app)
    assert c.get("/health").status_code == 200
    assert c.get("/plugin.json").status_code == 200
    r = c.get("/")
    assert r.status_code == 200
    assert "UxWebRTC" in r.text
