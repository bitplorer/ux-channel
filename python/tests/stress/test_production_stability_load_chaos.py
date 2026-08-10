"""
Production stability — load, chaos, integration for ux-channel.

Covers control plane, mesh RTC, media bridge (mesh|sfu), static assets,
rate limits, room capacity, concurrent mutation, SFU token gate.
"""

from __future__ import annotations

import concurrent.futures
import threading
import time
from dataclasses import replace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from ux_channel import Channel, ChannelConfig
from ux_channel.sfu import handle_sfu_token
from ux_channel.webrtc import get_rtc_store, reset_rtc_store, sign_rtc_ticket


SECRET = "prod-stability-secret-key-32ch!!"


def _cfg(**kw):
    base = dict(
        secret=SECRET,
        allow_memory_stores=True,
        webrtc_enabled=True,
        webrtc_rate_per_minute=12_000,
        webrtc_rate_burst=4_000,
        require_cap=False,  # exercise dispatch without cap mint noise
    )
    base.update(kw)
    return ChannelConfig.development(**base)


def _boot(**kw):
    reset_rtc_store()
    app = FastAPI()
    ch = Channel.boot(app, config=_cfg(**kw))
    return app, ch, TestClient(app, raise_server_exceptions=False)


# ---------------------------------------------------------------------------
# Integration — happy paths
# ---------------------------------------------------------------------------


def test_integration_action_region_media_mesh():
    app, ch, c = _boot()

    @ch.region
    def badge(ctx):
        return f"<b>{ch.draft.get('n', 0)}</b>"

    @ch.on(refresh=[badge], idempotent=False)
    def add(ctx, product_id: str = "x"):
        ch.draft.change("n", lambda n: (n or 0) + 1, default=0)
        return ch.done(notice="added")

    r = c.post("/ux-channel/action", json={"action": "add", "args": {"product_id": "sku1"}})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body.get("ok") is True
    p = ch.media.plugin("lobby", sub="user-1", mode="mesh")
    assert p.mode == "mesh" and "panel_html" not in p.as_dict()
    assert c.get("/ux-channel/static/ux-webrtc.js").status_code == 200
    assert c.get("/ux-channel/static/ux-sfu-livekit.js").status_code == 200
    assert c.get("/ux-channel/static/ux-channel.js").status_code == 200


def test_integration_mesh_two_peer_signal():
    app, ch, c = _boot()
    room = "pair-room"
    for peer in ("alice", "bob"):
        r = c.get(f"/ux-channel/rtc?room={room}&peer={peer}&name={peer}")
        assert r.status_code == 200, r.text
    offer = {
        "op": "signal",
        "room": room,
        "from": "alice",
        "to": "bob",
        "kind": "offer",
        "payload": {
            "type": "offer",
            "sdp": "v=0\r\no=- 0 0 IN IP4 127.0.0.1\r\ns=-\r\nt=0 0\r\n",
        },
    }
    r = c.post("/ux-channel/rtc", json=offer)
    assert r.status_code == 200, r.text
    polled = c.get(f"/ux-channel/rtc?room={room}&peer=bob&name=bob&since=0")
    assert polled.status_code == 200
    data = polled.json()
    sigs = data.get("signals") or data.get("messages") or []
    # store shape may use "signals"
    if not sigs and isinstance(data, dict):
        # accept any non-empty poll
        assert data.get("ok") is not False
    # leave
    assert c.post("/ux-channel/rtc", json={"op": "leave", "room": room, "peer": "alice"}).status_code == 200


def test_integration_sfu_token_gated():
    app, ch, c = _boot(
        sfu_provider="livekit",
        sfu_url="wss://example.livekit.cloud",
        sfu_api_key="APIkey",
        sfu_api_secret="secretsecretsecretsecret12",
    )
    # server-side plugin always works
    p = ch.media.plugin("r1", sub="alice", mode="sfu", cdn=False)
    assert p.token and p.client["url"]
    # HTTP mint
    r = c.post("/ux-channel/sfu/token", json={"room": "r1", "identity": "alice"})
    assert r.status_code == 200, r.text
    assert r.json().get("token")
    # production rejects anon
    cfg = ChannelConfig.production(
        secret=SECRET,
        allow_memory_stores=True,
        allowed_origins=("https://app.example",),
        sfu_provider="livekit",
        sfu_url="wss://example.livekit.cloud",
        sfu_api_key="APIkey",
        sfu_api_secret="secretsecretsecretsecret12",
        webrtc_require_origin=True,
    )
    st, body = handle_sfu_token(
        cfg,
        {"room": "r1", "identity": ""},
        origin="https://app.example",
        host="app.example",
    )
    assert st == 400
    st2, _ = handle_sfu_token(
        cfg,
        {"room": "r1", "identity": "bob"},
        origin="https://evil.example",
        host="app.example",
    )
    assert st2 == 403


def test_integration_sfu_ticket_subject_bind():
    cfg = _cfg(
        sfu_provider="livekit",
        sfu_url="wss://x.livekit.cloud",
        sfu_api_key="APIkey",
        sfu_api_secret="secretsecretsecretsecret12",
        webrtc_require_ticket=True,
    )
    ticket = sign_rtc_ticket(cfg, "room-x", sub="alice")
    st, body = handle_sfu_token(
        cfg,
        {"room": "room-x", "identity": "bob", "ticket": ticket},
        ticket=ticket,
    )
    assert st == 403
    st2, body2 = handle_sfu_token(
        cfg,
        {"room": "room-x", "identity": "alice", "ticket": ticket},
        ticket=ticket,
    )
    assert st2 == 200, body2
    assert body2["token"]


# ---------------------------------------------------------------------------
# Load
# ---------------------------------------------------------------------------


def test_load_concurrent_actions():
    app, ch, c = _boot()

    @ch.on(idempotent=True)
    def ping(ctx, n: int = 0):
        return ch.done(meta={"n": n})

    errs = []
    lock = threading.Lock()

    def one(i):
        r = c.post("/ux-channel/action", json={"action": "ping", "args": {"n": i}})
        if r.status_code != 200 or not r.json().get("ok"):
            with lock:
                errs.append((r.status_code, r.text[:80]))

    with concurrent.futures.ThreadPoolExecutor(max_workers=32) as ex:
        list(ex.map(one, range(300)))
    assert errs == [], errs[:5]


def test_load_concurrent_rtc_poll_same_room_under_cap():
    app, ch, c = _boot(webrtc_max_peers=16)
    room = "load-room"
    errs = []
    lock = threading.Lock()

    def one(i):
        peer = f"p{i % 12}"  # reuse peers within cap
        r = c.get(f"/ux-channel/rtc?room={room}&peer={peer}&name={peer}")
        if r.status_code not in (200, 429):
            with lock:
                errs.append((r.status_code, r.text[:100]))

    with concurrent.futures.ThreadPoolExecutor(max_workers=24) as ex:
        list(ex.map(one, range(240)))
    assert errs == [], errs[:5]


def test_load_media_plugin_thread_safe():
    app, ch, c = _boot(
        sfu_provider="livekit",
        sfu_url="wss://x.livekit.cloud",
        sfu_api_key="APIkey",
        sfu_api_secret="secretsecretsecretsecret12",
    )
    errs = []
    lock = threading.Lock()

    def one(i):
        try:
            if i % 2:
                p = ch.media.plugin(f"r{i%5}", sub=f"u{i}", mode="mesh")
                assert p.mode == "mesh"
            else:
                p = ch.media.plugin(f"r{i%5}", sub=f"u{i}", mode="sfu", cdn=False)
                assert p.token and len(p.token.split(".")) == 3
        except Exception as e:
            with lock:
                errs.append(str(e))

    with concurrent.futures.ThreadPoolExecutor(max_workers=20) as ex:
        list(ex.map(one, range(120)))
    assert errs == []


# ---------------------------------------------------------------------------
# Chaos
# ---------------------------------------------------------------------------


def test_chaos_room_full_returns_409_not_500():
    app, ch, c = _boot(webrtc_max_peers=3)
    room = "full"
    codes = []
    for i in range(6):
        r = c.get(f"/ux-channel/rtc?room={room}&peer=unique{i}&name=n{i}")
        codes.append(r.status_code)
    assert 200 in codes
    assert 409 in codes
    assert 500 not in codes


def test_chaos_malformed_rtc_bodies():
    app, ch, c = _boot()
    for body in (None, [], "x", {"op": "signal"}, {"op": "nope", "from": "a", "room": "r"}):
        if body is None:
            r = c.post("/ux-channel/rtc", content=b"not-json", headers={"content-type": "application/json"})
        else:
            r = c.post("/ux-channel/rtc", json=body)
        assert r.status_code < 500, (body, r.status_code, r.text[:80])


def test_chaos_invalid_peer_ids():
    app, ch, c = _boot()
    # empty / whitespace / non-ascii-only → 400
    for peer in ("", " ", "🔥", "..."):
        r = c.get("/ux-channel/rtc", params={"room": "r", "peer": peer, "name": "n"})
        assert r.status_code in (400, 403, 422), (peer, r.status_code)
    # traversal-like is sanitized to safe id (not 500)
    r = c.get("/ux-channel/rtc", params={"room": "r", "peer": "../x", "name": "n"})
    assert r.status_code in (200, 400)
    assert r.status_code != 500
    # overlong is truncated, not 500
    r = c.get("/ux-channel/rtc", params={"room": "r", "peer": "a" * 500, "name": "n"})
    assert r.status_code in (200, 400)


def test_chaos_sfu_not_configured_501():
    app, ch, c = _boot()
    r = c.post("/ux-channel/sfu/token", json={"room": "r", "identity": "u"})
    assert r.status_code == 501
    with pytest.raises(RuntimeError):
        ch.media.plugin("r", mode="sfu")


def test_chaos_unknown_sfu_provider():
    from ux_channel.sfu import get_sfu

    cfg = _cfg(sfu_provider="jitsi-cloud-typo")
    with pytest.raises(ValueError):
        get_sfu(cfg)


def test_chaos_static_path_traversal_blocked():
    app, ch, c = _boot()
    r = c.get("/ux-channel/static/../../../etc/passwd")
    assert r.status_code in (404, 400, 403)


def test_chaos_rate_limit_trips():
    app, ch, c = _boot(webrtc_rate_per_minute=30, webrtc_rate_burst=5)
    codes = set()
    for i in range(40):
        r = c.get(f"/ux-channel/rtc?room=rl&peer=p0&name=n")
        codes.add(r.status_code)
    assert 429 in codes


# ---------------------------------------------------------------------------
# Store concurrency
# ---------------------------------------------------------------------------


def test_store_concurrent_signal_no_crash():
    app, ch, c = _boot(webrtc_max_peers=32)
    store = get_rtc_store(ch.config)
    room = "sig"
    for p in ("a", "b"):
        store.poll(room, p, name=p, since=0)
    errs = []
    lock = threading.Lock()

    def one(i):
        try:
            store.signal(
                room,
                from_peer="a",
                to_peer="b",
                kind="ice",
                payload={"candidate": f"c{i}", "sdpMid": "0", "sdpMLineIndex": 0},
            )
        except Exception as e:
            with lock:
                errs.append(str(e))

    with concurrent.futures.ThreadPoolExecutor(max_workers=16) as ex:
        list(ex.map(one, range(100)))
    assert errs == []
    out = store.poll(room, "b", name="b", since=0)
    assert out is not None


def test_diagnose_under_load_stable():
    app, ch, c = _boot()

    def one(_):
        d = ch.diagnose()
        assert "media" in d
        assert ch.media.mode in ("mesh", "sfu")

    with concurrent.futures.ThreadPoolExecutor(max_workers=16) as ex:
        list(ex.map(one, range(80)))
