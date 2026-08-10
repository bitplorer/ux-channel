"""Unified ch.media bridge — mesh + LiveKit SFU plugins."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from ux_channel import Channel, ChannelConfig
from ux_channel.dx import DAY1_CHANNEL_API
from ux_channel.media import DAY1_MEDIA_API


def _boot(**kw):
    app = FastAPI()
    base = dict(
        secret="dev-secret-key-32chars-minimum!!!!",
        allow_memory_stores=True,
        webrtc_enabled=True,
    )
    base.update(kw)
    ch = Channel.boot(app, config=ChannelConfig.development(**base))
    return app, ch


def test_day1_includes_media():
    assert "media" in DAY1_CHANNEL_API
    for name in DAY1_MEDIA_API:
        assert name in (
            "plugin",
            "session",
            "mesh",
            "sfu",
            "mode",
            "diagnose",
            "ice",
        )


def test_default_mesh_plugin():
    app, ch = _boot()
    assert ch.media.mode == "mesh"
    p = ch.media.plugin("lobby", sub="u1")
    assert p.mode == "mesh" and p.provider == "mesh"
    assert p.client.get("provider") == "mesh"
    assert "iceUrl" in p.client or "rtcPath" in p.client
    assert "panel_html" not in p.as_dict()
    assert "scripts_html" not in p.as_dict()
    assert p.scripts or p.client
    assert "data-channel-media-mode" in p.attrs


def test_sfu_plugin_livekit():
    app, ch = _boot(
        sfu_provider="livekit",
        sfu_url="wss://example.livekit.cloud",
        sfu_api_key="APItestkey",
        sfu_api_secret="secretsecretsecretsecret12",
    )
    assert ch.media.mode == "sfu"
    p = ch.media.plugin("room-a", sub="alice", cdn=True)
    assert p.mode == "sfu" and p.provider == "livekit"
    assert p.token and p.client["token"] == p.token
    assert p.client["url"]
    srcs = " ".join(s.src for s in p.scripts)
    assert "livekit-client" in srcs or "ux-sfu" in srcs
    assert p.client.get("token")
    # force mesh even when sfu configured
    m = ch.media.plugin("room-a", sub="alice", mode="mesh")
    assert m.mode == "mesh"


def test_sfu_plugin_requires_config():
    app, ch = _boot()
    try:
        ch.media.plugin("r", mode="sfu")
        assert False, "expected RuntimeError"
    except RuntimeError as e:
        assert "SFU" in str(e)


def test_static_sfu_boot_js():
    app, ch = _boot()
    r = TestClient(app).get("/ux-channel/static/ux-sfu-livekit.js")
    assert r.status_code == 200
    assert "UidMedia" in r.text


def test_diagnose_media():
    app, ch = _boot()
    d = ch.diagnose()
    assert "media" in d
    assert d["media"]["default_mode"] == "mesh"
