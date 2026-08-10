"""ICE DX: one rule html vs live, low cognitive load, consistent wiring."""

from __future__ import annotations

import os

from fastapi import FastAPI
from fastapi.testclient import TestClient

from ux_channel import Channel, ChannelConfig
from ux_channel.host.dx import DAY1_WEBRTC_API
from ux_channel.realtime.webrtc import IceAccess


def _ch(monkeypatch=None, **kw):
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


def test_public_api_includes_ice():
    assert "ice" in DAY1_WEBRTC_API


def test_ice_html_never_has_credentials(monkeypatch):
    monkeypatch.setenv("UX_CHANNEL_TURN_URLS", "turn:evil.example:3478")
    monkeypatch.setenv("UX_CHANNEL_TURN_SECRET", "secret")
    monkeypatch.setenv("UX_CHANNEL_TURN_USER", "static-user")
    monkeypatch.setenv("UX_CHANNEL_TURN_PASS", "static-pass")
    app, ch = _ch()
    html = ch.webrtc.ice.servers()
    assert all(not s.get("credential") and not s.get("username") for s in html)
    # body attrs use html only
    blob = ch.webrtc.body_attrs(room="r").get("data-channel-webrtc-ice", "")
    assert "credential" not in blob and "static-pass" not in blob
    assert ch.webrtc.body_attrs(room="r")["data-channel-webrtc-ice-url"] == ch.webrtc.ice.url


def test_ice_live_can_include_turn(monkeypatch):
    monkeypatch.setenv("UX_CHANNEL_TURN_URLS", "turn:t.example:3478")
    monkeypatch.setenv("UX_CHANNEL_TURN_SECRET", "sec")
    app, ch = _ch()
    live = ch.webrtc.ice.live(sub="alice")
    assert any(s.get("credential") for s in live)
    # aliases match
    assert ch.webrtc.public_ice_servers() == ch.webrtc.ice.servers()
    live2 = ch.webrtc.ice_servers(sub="alice")
    assert any(s.get("credential") for s in live2)


def test_plugin_wires_html_and_url(monkeypatch):
    monkeypatch.setenv("UX_CHANNEL_TURN_URLS", "turn:t.example:3478")
    monkeypatch.setenv("UX_CHANNEL_TURN_SECRET", "sec")
    app, ch = _ch()
    p = ch.webrtc.plugin("lobby", sub="u")
    assert p.client["iceUrl"] == ch.webrtc.ice.url
    assert not any(
        (s.get("credential") for s in p.client.get("iceServers") or [])
    )
    assert "client_json" in p.as_dict()


def test_ice_access_type():
    app, ch = _ch()
    assert isinstance(ch.webrtc.ice, IceAccess)
    assert ch.webrtc.ice.url.endswith("/rtc/ice")
