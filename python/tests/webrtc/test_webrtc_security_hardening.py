"""Security + brittle-edge coverage for WebRTC plane (0.1 hardening)."""

from __future__ import annotations

import pytest

from ux_channel.host.config import ChannelConfig
from ux_channel.realtime.webrtc import (
    WebRTCPlane,
    _peer_id_ok,
    _sanitize_id,
    allow_rtc_traffic,
    get_rtc_store,
    reset_rtc_store,
    sign_rtc_ticket,
)
from ux_channel.realtime.webrtc_http import handle_rtc_poll, handle_rtc_post


@pytest.fixture(autouse=True)
def _clean_store():
    reset_rtc_store()
    yield
    reset_rtc_store()


def test_sanitize_strips_dangerous():
    assert _sanitize_id("../etc/passwd") == "etcpasswd" or "passwd" in _sanitize_id("../etc/passwd")
    assert "/" not in _sanitize_id("a/b")
    assert len(_sanitize_id("x" * 100)) == 64


def test_peer_min_length():
    cfg = ChannelConfig.development(
        secret="dev-secret-key-32chars-minimum!!!!",
        webrtc_min_peer_len=4,
    )
    assert not _peer_id_ok("ab", cfg)
    assert _peer_id_ok("abcd", cfg)
    assert _peer_id_ok("p_" + "x" * 8, cfg)


def test_poll_rejects_short_peer_when_configured():
    cfg = ChannelConfig.development(
        secret="dev-secret-key-32chars-minimum!!!!",
        allow_memory_stores=True,
        webrtc_require_ticket=False,
        webrtc_min_peer_len=4,
    )
    status, body = handle_rtc_poll(cfg, room="r", peer="ab")
    assert status == 400
    assert "peer" in body["error"]


def test_poll_rejects_empty_peer():
    cfg = ChannelConfig.development(
        secret="dev-secret-key-32chars-minimum!!!!",
        allow_memory_stores=True,
        webrtc_require_ticket=False,
    )
    status, body = handle_rtc_poll(cfg, room="r", peer="")
    assert status == 400


def test_poll_ok_long_peer():

    cfg = ChannelConfig.development(
        secret="dev-secret-key-32chars-minimum!!!!",
        allow_memory_stores=True,
        webrtc_require_ticket=False,
    )
    status, body = handle_rtc_poll(cfg, room="r", peer="peer_alice_1")
    assert status == 200
    assert "peers" in body


def test_ticket_required_in_production_defaults():
    cfg = ChannelConfig.production("prod-secret-key-at-least-32-chars!!")
    assert cfg.webrtc_require_ticket is True
    assert cfg.webrtc_require_origin is True
    status, body = handle_rtc_poll(cfg, room="lobby", peer="peer_ok_1")
    assert status == 403


def test_ticket_allows_when_required():
    cfg = ChannelConfig.production("prod-secret-key-at-least-32-chars!!")
    # production may warn on memory stores
    ticket = sign_rtc_ticket(cfg, "lobby", sub="u1")
    status, body = handle_rtc_poll(
        cfg, room="lobby", peer="peer_ok_1", ticket=ticket
    )
    assert status == 200


def test_rate_limit_trips():
    cfg = ChannelConfig.development(
        secret="dev-secret-key-32chars-minimum!!!!",
        allow_memory_stores=True,
        webrtc_require_ticket=False,
        webrtc_rate_per_minute=30,
        webrtc_rate_burst=3,
    )
    # reset limiter by using unique peer
    peer = "ratepeer_xyz"
    codes = []
    for _ in range(10):
        st, _ = handle_rtc_poll(cfg, room="rate_room", peer=peer, client_key="ip1")
        codes.append(st)
    assert 429 in codes, codes


def test_public_ice_strips_credentials():
    class C:
        config = ChannelConfig.development(
            secret="dev-secret-key-32chars-minimum!!!!",
            allow_memory_stores=True,
            webrtc_ice_servers=(
                {"urls": "stun:stun.l.google.com:19302"},
                {
                    "urls": "turn:turn.example.com",
                    "username": "u",
                    "credential": "secret",
                },
            ),
        )
        path = "/ux-channel"

    plane = WebRTCPlane(channel=C())
    pub = plane.public_ice_servers()
    assert all("credential" not in s and "username" not in s for s in pub)
    attrs = plane.body_attrs(room="x")
    assert "credential" not in attrs.get("data-channel-webrtc-ice", "")


def test_store_fingerprint_rebuilds_max_peers():
    cfg1 = ChannelConfig.development(
        secret="dev-secret-key-32chars-minimum!!!!",
        allow_memory_stores=True,
        webrtc_max_peers=2,
    )
    s1 = get_rtc_store(cfg1)
    assert s1.max_peers == 2
    cfg2 = ChannelConfig.development(
        secret="dev-secret-key-32chars-minimum!!!!",
        allow_memory_stores=True,
        webrtc_max_peers=5,
    )
    s2 = get_rtc_store(cfg2)
    assert s2.max_peers == 5


def test_signal_invalid_kind():
    cfg = ChannelConfig.development(
        secret="dev-secret-key-32chars-minimum!!!!",
        allow_memory_stores=True,
        webrtc_require_ticket=False,
    )
    st, body = handle_rtc_post(
        cfg,
        {
            "op": "signal",
            "room": "r",
            "from": "peer_a_xx",
            "to": "peer_b_yy",
            "kind": "hack",
            "payload": {},
        },
    )
    assert st == 400
