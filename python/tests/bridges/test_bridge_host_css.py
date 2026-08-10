"""Placement may carry class/style for UxDom; package props stay in mount_props."""

from fastapi import FastAPI

from ux_channel import Channel, ChannelConfig
from ux_channel.bridge_style import merge_host_style


def _ch():
    return Channel.boot(
        FastAPI(),
        config=ChannelConfig.development(
            secret="dev-secret-key-32chars-minimum!!!!",
            allow_memory_stores=True,
            require_cap=False,
        ),
    )


def test_merge_host_style_helper():
    s = merge_host_style(css={"--accent": "#f00"}, style="height: 10rem")
    assert "--accent: #f00" in s
    assert "height: 10rem" in s


def test_mount_spec_optional_class_for_ux_dom_not_npm():
    """class/style on mount_spec are element chrome for UxDom — not npm props."""
    ch = _ch()
    spec = ch.bridge.mount_spec(
        "c1",
        package="chart.js",
        props={"type": "bar", "options": {"responsive": True}},
        class_name="h-80",
        style="min-height: 12rem",
    )
    assert spec.attrs.get("class") == "h-80"
    assert "min-height" in spec.attrs.get("style", "")
    assert "options" in spec.attrs["data-channel-bridge-props"]
    assert "css" not in spec.attrs["data-channel-bridge-props"]
