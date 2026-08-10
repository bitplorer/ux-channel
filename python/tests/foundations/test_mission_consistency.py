"""Library mission consistency: capabilities intact, no UI-boundary bloat."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from ux_channel import Channel, ChannelConfig, Intent, __all__ as ROOT_ALL
from ux_channel.render.kit import attr_string, demo_button, demo_page, demo_scripts, script_tags
from ux_channel.host.channel import CHANNEL_PUBLIC_API, DAY1_WEBRTC_API
from ux_channel.realtime.webrtc import WebRTCPlane, reset_rtc_store
from ux_channel.realtime.webrtc_http import handle_rtc_poll, handle_rtc_post
from ux_channel.realtime.webrtc_ui import RtcPlugin, RtcSession


def test_root_excludes_webrtc_internals():
    for name in ("sign_rtc_ticket", "WebRTCPlane", "RtcSession", "RtcPlugin", "MemoryRtcStore"):
        assert name not in ROOT_ALL


def test_webrtc_day1_is_plugin_not_ui():
    assert "plugin" in DAY1_WEBRTC_API
    assert "session" not in DAY1_WEBRTC_API  # public API is plugin; session is power
    assert "page" not in DAY1_WEBRTC_API and "panel" not in DAY1_WEBRTC_API
    assert not hasattr(WebRTCPlane, "page")
    assert not hasattr(WebRTCPlane, "panel")
    assert not hasattr(RtcSession, "panel_html")
    assert not hasattr(RtcSession, "page_html")
    assert "panel_html" not in RtcPlugin.__dataclass_fields__


def test_core_and_webrtc_capabilities_together():
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

    @ch.on(idempotent=False)
    def ping(x: int = 0):
        return ch.done(notice=f"x={x}")

    cap = ch.registry.mint("ping", {"x": 1})
    r = ch.registry.dispatch(Intent(action="ping", args={"x": 1}, cap=cap))
    assert r.ok

    p = ch.webrtc.plugin("room1")
    assert p.path.endswith("/rtc")
    assert "scripts_html" in p.as_dict() and "client" in p.as_dict()
    assert "panel_html" not in p.as_dict()

    st, body = handle_rtc_poll(ch.config, room="room1", peer="peer_a_ok")
    assert st == 200
    st, _ = handle_rtc_post(
        ch.config,
        {
            "op": "signal",
            "room": "room1",
            "from": "peer_a_ok",
            "to": "peer_b_ok",
            "kind": "ice-done",
            "payload": None,
        },
    )
    assert st == 200

    # static + scripts
    c = TestClient(app)
    assert c.get("/ux-channel/static/ux-webrtc.js").status_code == 200
    assert "ux-webrtc" in str(demo_scripts(ch, ))
    # body attrs still wire webrtc
    ba = attr_string(ch.body_attrs(webrtc="room1"))
    assert "data-channel-webrtc-room" in ba
    assert "credential" not in ba

    for name in CHANNEL_PUBLIC_API:
        assert hasattr(ch, name) or name in ("boot",), name
    for name in DAY1_WEBRTC_API:
        assert hasattr(ch.webrtc, name), name


def test_production_security_defaults_not_weakened():
    cfg = ChannelConfig.production("prod-secret-key-at-least-32-chars!!")
    assert cfg.require_cap is True
    assert cfg.webrtc_require_ticket is True
    assert cfg.webrtc_require_origin is True
    assert cfg.expose_internal_errors is False
