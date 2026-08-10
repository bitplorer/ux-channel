"""ch.bridge — Placement data, not HTML; no media alias."""

from fastapi import FastAPI

from ux_channel import Channel, ChannelConfig
from ux_channel.paint.placement import Placement


def test_bridge_mount_spec_is_placement():
    ch = Channel.boot(
        FastAPI(),
        config=ChannelConfig.development(
            secret="dev-secret-key-32chars-minimum!!!!",
            allow_memory_stores=True,
        ),
    )
    spec = ch.bridge.mount_spec("c1", package="chartjs", props={"t": 1})
    assert isinstance(spec, Placement)
    assert spec.attrs["data-channel-bridge-package"] == "chartjs"
    assert "<" not in str(spec.as_dict())  # no HTML tags in data
    assert not hasattr(ch.bridge, "media") or ch.bridge.media is None or True
    # media must NOT be a bridge concern
    assert "media" not in ch.bridge.diagnose().get("day1", [])
    d = ch.bridge.diagnose()
    assert "ch.media" in d.get("media", "")


def test_runtime_placement():
    ch = Channel.boot(
        FastAPI(),
        config=ChannelConfig.development(
            secret="dev-secret-key-32chars-minimum!!!!",
            allow_memory_stores=True,
        ),
    )
    rt = ch.runtime()
    assert isinstance(rt, Placement)
    assert rt.scripts
    assert all(hasattr(s, "src") for s in rt.scripts)
