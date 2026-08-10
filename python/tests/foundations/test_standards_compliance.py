"""RFC/JSEP-shaped compliance + SoC boundary checks."""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from ux_channel import Channel, ChannelConfig
from ux_channel.realtime.webrtc import (
    SIGNAL_KINDS,
    reset_rtc_store,
    validate_signal_payload,
)
from ux_channel.realtime.webrtc_http import handle_rtc_post


def test_signal_kinds_match_jsep_ferry():
    assert SIGNAL_KINDS == frozenset({"offer", "answer", "ice", "ice-done"})


def test_validate_offer_answer_jsep_shape():
    o = validate_signal_payload(
        "offer", {"type": "offer", "sdp": "v=0\r\no=- 0 0 IN IP4 0.0.0.0\r\ns=-\r\nt=0 0\r\n"}
    )
    assert o["type"] == "offer" and "v=" in o["sdp"]
    with pytest.raises(ValueError):
        validate_signal_payload("offer", {"type": "answer", "sdp": "v=0"})
    with pytest.raises(ValueError):
        validate_signal_payload("offer", {"type": "offer", "sdp": "not-sdp"})
    with pytest.raises(ValueError):
        validate_signal_payload("offer", "raw-string")


def test_validate_ice_and_ice_done():
    assert validate_signal_payload("ice", {"candidate": "a=candidate:1...", "sdpMid": "0"})
    assert validate_signal_payload("ice-done", None) is None
    with pytest.raises(ValueError):
        validate_signal_payload("ice-done", {"nope": 1})
    with pytest.raises(ValueError):
        validate_signal_payload("ice", "candidate-string")


def test_store_rejects_bad_offer():
    reset_rtc_store()
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
            "kind": "offer",
            "payload": {"type": "offer", "sdp": "garbage-without-version"},
        },
    )
    assert st == 400


def test_rtc_http_cache_headers():
    reset_rtc_store()
    app = FastAPI()
    Channel.boot(
        app,
        config=ChannelConfig.development(
            secret="dev-secret-key-32chars-minimum!!!!",
            allow_memory_stores=True,
            webrtc_require_ticket=False,
        ),
    )
    c = TestClient(app)
    r = c.get("/ux-channel/rtc", params={"room": "r", "peer": "peer_std_1"})
    assert r.status_code == 200
    assert "no-store" in r.headers.get("cache-control", "").lower()


def test_soc_no_media_plane_in_plugin():
    """Channel plugin must not claim media/SFU ownership."""
    app = FastAPI()
    ch = Channel.boot(
        app,
        config=ChannelConfig.development(
            secret="dev-secret-key-32chars-minimum!!!!",
            allow_memory_stores=True,
        ),
    )
    p = ch.webrtc.plugin("lobby").as_dict()
    assert "panel_html" not in p
    assert "sfu" not in p
    # ice split is standards-aligned placement
    assert "iceUrl" in p["client"] and "iceServers" in p["client"]
