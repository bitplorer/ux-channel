"""Python ↔ ux-webrtc.js wire contract consistency."""

from __future__ import annotations

import re
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from ux_channel import Channel, ChannelConfig
from ux_channel.webrtc import SIGNAL_KINDS, validate_signal_payload, reset_rtc_store

JS = Path(__file__).resolve().parents[2] / "src/ux_channel/static/ux-webrtc.js"


def test_js_file_documents_wire_contract():
    text = JS.read_text(encoding="utf-8")
    assert "offer | answer | ice | ice-done" in text
    assert "iceUrl" in text and "_refreshIce" in text
    assert "WEBRTC_VERSION" in text or "version:" in text
    assert "SIGNAL_KINDS" in text
    assert "addIceCandidate(null)" in text or "ice-done" in text
    # kinds constant matches Python
    m = re.search(r'SIGNAL_KINDS:\s*\[([^\]]+)\]', text)
    assert m, "UxWebRTC.SIGNAL_KINDS missing"
    kinds = {x.strip().strip("\"'") for x in m.group(1).split(",")}
    assert kinds == set(SIGNAL_KINDS)


def test_browser_like_jsep_payloads_roundtrip_http():
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
    c.get("/ux-channel/rtc", params={"room": "w", "peer": "peer_alice1", "since": 0})
    c.get("/ux-channel/rtc", params={"room": "w", "peer": "peer_bob222", "since": 0})
    sdp = "v=0\r\no=- 1 1 IN IP4 127.0.0.1\r\ns=-\r\nt=0 0\r\nm=audio 9 UDP/TLS/RTP/SAVPF 111\r\n"
    # offer as browser localDescription JSON
    r = c.post(
        "/ux-channel/rtc",
        json={
            "op": "signal",
            "room": "w",
            "from": "peer_alice1",
            "to": "peer_bob222",
            "kind": "offer",
            "payload": {"type": "offer", "sdp": sdp},
        },
    )
    assert r.status_code == 200, r.text
    r = c.post(
        "/ux-channel/rtc",
        json={
            "op": "signal",
            "room": "w",
            "from": "peer_alice1",
            "to": "peer_bob222",
            "kind": "ice",
            "payload": {
                "candidate": "candidate:1 1 UDP 2122252543 1.2.3.4 12345 typ host",
                "sdpMid": "0",
                "sdpMLineIndex": 0,
            },
        },
    )
    assert r.status_code == 200
    r = c.post(
        "/ux-channel/rtc",
        json={
            "op": "signal",
            "room": "w",
            "from": "peer_alice1",
            "to": "peer_bob222",
            "kind": "ice-done",
            "payload": None,
        },
    )
    assert r.status_code == 200
    inbox = c.get(
        "/ux-channel/rtc", params={"room": "w", "peer": "peer_bob222", "since": 0}
    ).json()
    kinds = [s["kind"] for s in inbox.get("signals") or []]
    assert "offer" in kinds and "ice" in kinds and "ice-done" in kinds


def test_plugin_client_matches_js_join_opts():
    app = FastAPI()
    ch = Channel.boot(
        app,
        config=ChannelConfig.development(
            secret="dev-secret-key-32chars-minimum!!!!",
            allow_memory_stores=True,
        ),
    )
    client = ch.webrtc.plugin("lobby").client
    # keys UidRtcRoom constructor reads
    for k in ("room", "rtcPath", "wsPath", "iceServers", "iceUrl"):
        assert k in client
    assert client["iceUrl"] == ch.webrtc.ice.url
    assert client["iceServers"] == ch.webrtc.ice.servers()
    # no credentials in seed
    assert not any(s.get("credential") for s in client["iceServers"])


def test_validate_matches_js_security_notes_kinds():
    for kind in SIGNAL_KINDS:
        if kind == "ice-done":
            assert validate_signal_payload(kind, None) is None
        elif kind == "ice":
            validate_signal_payload(kind, {"candidate": "x", "sdpMid": "0"})
        else:
            validate_signal_payload(
                kind, {"type": kind, "sdp": "v=0\r\no=- 0 0 IN IP4 0.0.0.0\r\ns=-\r\nt=0 0\r\n"}
            )
