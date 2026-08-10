"""Interop layer only — uses channel + duck trees (UxDom optional)."""

from __future__ import annotations

from fastapi import FastAPI

from ux_channel import Channel, ChannelConfig
from ux_channel.capability import CapabilityService
from ux_channel.attenuate import attenuate
from ux_channel_ux_dom import compile_ux_dom, control_ux_dom, paint_ux_dom_region, tree_to_dict
from ux_channel_ux_dom.tree import attenuate_control


SECRET = "glue-test-secret-key-32bytes-min!!!"


def test_control_ux_dom_keys():
    app = FastAPI()
    ch = Channel.boot(
        app,
        config=ChannelConfig.development(
            secret=SECRET, allow_memory_stores=True, require_cap=False
        ),
    )

    @ch.on
    def add():
        pass

    attrs = control_ux_dom(ch, add, trust_sku="x")
    assert any("action" in k for k in attrs)
    assert any("cap" in k for k in attrs)


def test_tree_compile_and_paint_duck():
    tree = {
        "tag": "div",
        "children": [{"tag": "span", "children": [], "key": "n"}],
    }
    d = tree_to_dict(tree)
    sm = compile_ux_dom(d, prefix="x")
    assert sm.uids
    ops = paint_ux_dom_region(
        {"tag": "div", "attrs": {"data-channel-id": "box"}, "children": [{"tag": "#text", "text": "hi"}]},
        uid="box",
    )
    assert ops[0]["op"] == "morph"
    assert "hi" in ops[0]["html"]


def test_attenuate_control_glue():
    app = FastAPI()
    ch = Channel.boot(
        app,
        config=ChannelConfig.development(
            secret=SECRET, allow_memory_stores=True, require_cap=True
        ),
    )
    caps = ch.registry._caps
    parent = attenuate(caps, "pay", {"order_id": "1"}, caveats=["pay"])
    attrs = attenuate_control(
        ch, "pay", parent_cap=parent, caveats=["pay"], trust_order_id="1"
    )
    assert any("cap" in k for k in attrs)
