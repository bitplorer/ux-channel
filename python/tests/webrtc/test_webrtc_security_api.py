"""DTLS/simulcast docs posture + API pattern + diagnose security fields."""

from ux_channel import Channel, ChannelConfig
from ux_channel.host.channel import WEBRTC_PUBLIC_API
from ux_channel.realtime.webrtc import WebRTCPlane, reset_rtc_store


def test_public_api_webrtc_api_minimal():
    assert "sign_ticket" in WEBRTC_PUBLIC_API
    assert "diagnose" in WEBRTC_PUBLIC_API
    # power methods stay off public API list
    assert "store" not in WEBRTC_PUBLIC_API
    assert "default_ice_servers" not in WEBRTC_PUBLIC_API


def test_diagnose_security_posture():
    reset_rtc_store()
    cfg = ChannelConfig.development(
        secret="dev-secret-key-32chars-minimum!!!!",
        allow_memory_stores=True,
        webrtc_require_ticket=True,
        webrtc_require_origin=True,
    )

    class _Ch:
        config = cfg
        path = "/ux-channel"

    d = WebRTCPlane(channel=_Ch()).diagnose()
    assert d["dtls_pinning"] is False
    assert d["security"]["dtls_cert_pinning"] == "unsupported_in_browser_webrtc"
    assert d["security"]["tickets"] is True
    assert d["security"]["html_ice_has_credentials"] is False
    assert d["require_ticket"] is True


def test_describe_mentions_webrtc():
    text = Channel.describe()
    assert "webrtc" in text.lower()


def test_client_js_has_simulcast_and_security_notes():
    from pathlib import Path

    js = (Path(__file__).resolve().parents[2] / "src" / "ux_channel" / "static" / "ux-webrtc.js").read_text()
    assert "simulcast" in js
    assert "setSimulcastLayers" in js
    assert "securityNotes" in js
    assert "iceTransportPolicy" in js
    assert "dtlsPinning" in js
