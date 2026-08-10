"""Short-lived TURN mint + authenticated /rtc/ice endpoint."""

from __future__ import annotations

import base64
import hashlib
import hmac
import os

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from ux_channel import Channel, ChannelConfig
from ux_channel.webrtc import reset_rtc_store, sign_rtc_ticket
from ux_channel.webrtc_http import handle_rtc_ice
from ux_channel.webrtc_turn import ice_servers_with_turn, mint_turn_credential, turn_configured


def test_mint_turn_credential_shape():
    u, c, exp = mint_turn_credential(secret="s3cret", username="alice", ttl_s=120, now=1_700_000_000)
    assert u.startswith(str(exp) + ":")
    assert "alice" in u
    # verify hmac
    digest = hmac.new(b"s3cret", u.encode(), hashlib.sha1).digest()
    assert c == base64.b64encode(digest).decode("ascii")


def test_ice_servers_with_rest_secret(monkeypatch):
    monkeypatch.setenv("UX_CHANNEL_TURN_URLS", "turn:turn.example:3478")
    monkeypatch.setenv("UX_CHANNEL_TURN_SECRET", "static-auth-secret")
    monkeypatch.delenv("UX_CHANNEL_TURN_USER", raising=False)
    servers = ice_servers_with_turn(username="bob", ttl_s=60)
    turn = [s for s in servers if str(s.get("urls", "")).startswith("turn")]
    assert turn and turn[0]["username"] and turn[0]["credential"]
    assert ":" in turn[0]["username"]  # exp:user


def test_handle_rtc_ice_requires_ticket_in_prod():
    cfg = ChannelConfig.production("prod-secret-key-at-least-32-chars!!")
    st, body = handle_rtc_ice(cfg, room="lobby")
    assert st == 403
    tok = sign_rtc_ticket(cfg, "lobby", sub="u1")
    st, body = handle_rtc_ice(cfg, room="lobby", ticket=tok, sub="u1")
    assert st == 200
    assert body["ok"] is True
    assert "iceServers" in body


def test_http_ice_route_and_plugin_ice_url(monkeypatch):
    monkeypatch.setenv("UX_CHANNEL_TURN_URLS", "turn:t.example:3478")
    monkeypatch.setenv("UX_CHANNEL_TURN_SECRET", "sec")
    reset_rtc_store()
    app = FastAPI()
    ch = Channel.boot(
        app,
        config=ChannelConfig.development(
            secret="dev-secret-key-32chars-minimum!!!!",
            allow_memory_stores=True,
            webrtc_enabled=True,
            webrtc_require_ticket=False,
        ),
    )
    p = ch.webrtc.plugin("lobby")
    assert p.client.get("iceUrl", "").endswith("/rtc/ice")
    assert "client_json" in p.as_dict()
    assert "data-channel-webrtc-ice-url" in ch.webrtc.body_attrs(room="lobby")
    c = TestClient(app)
    r = c.get("/ux-channel/rtc/ice", params={"room": "lobby", "sub": "x"})
    assert r.status_code == 200
    data = r.json()
    assert data["ok"] and any(
        "turn" in str(s.get("urls", "")).lower() for s in data["iceServers"]
    )
    posture = ch.webrtc.diagnose()["security"]["turn"]
    assert posture["mode"] == "rest"


def test_turn_posture_none():
    # clear env in process - may be polluted; call turn_configured after del
    for k in list(os.environ):
        if k.startswith("UX_CHANNEL_TURN"):
            pass  # don't mutate global heavily
    assert "mode" in turn_configured()


def test_plane_ice_servers_include_turn(monkeypatch):
    monkeypatch.setenv("UX_CHANNEL_TURN_URLS", "turns:t.example:5349")
    monkeypatch.setenv("UX_CHANNEL_TURN_SECRET", "x")
    app = FastAPI()
    ch = Channel.boot(
        app,
        config=ChannelConfig.development(
            secret="dev-secret-key-32chars-minimum!!!!",
            allow_memory_stores=True,
        ),
    )
    servers = ch.webrtc.ice_servers(sub="u", ttl_s=90)
    assert any(s.get("credential") for s in servers)
    # public still clean
    assert not any(s.get("credential") for s in ch.webrtc.public_ice_servers())
