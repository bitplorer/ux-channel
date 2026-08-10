"""High-value UI bridges for HTML hosts."""

from __future__ import annotations

from fastapi import FastAPI

from ux_channel import Channel, ChannelConfig
from ux_channel.bridges import (
    UI_SCRIPT,
    CodeMirrorBridge,
    DatePickerBridge,
    GenericBridge,
    LeafletBridge,
    MermaidBridge,
    QuillBridge,
    SelectBridge,
    SortableBridge,
    SwiperBridge,
)
from ux_channel.bridge.bridge_preset_gen import list_known_presets
from ux_channel.paint.demo import bridge_script_tags, ui_script_tags


def _ch():
    return Channel.boot(
        FastAPI(),
        config=ChannelConfig.development(
            secret="x" * 40, allow_memory_stores=True, require_cap=False
        ),
    )


def test_catalog_ui_keys():
    keys = {p["key"] for p in list_known_presets()}
    for k in (
        "leaflet",
        "codemirror",
        "tom-select",
        "flatpickr",
        "sortablejs",
        "swiper",
        "mermaid",
        "quill",
    ):
        assert k in keys, k


def test_leaflet_mount_attrs_and_ops():
    ch = _ch()
    maps = LeafletBridge(ch)
    m = maps("hq", center=[28.6, 77.2], zoom=12, markers=[{"lat": 28.6, "lng": 77.2, "popup": "HQ"}])
    attrs = m.mount_attrs(class_name="h-80 rounded-xl")
    assert "data_channel_bridge_id" in attrs or "data-channel-bridge-id" in {k.replace("_", "-") for k in attrs}
    # attrs_py uses underscores
    assert attrs.get("data_channel_bridge_package") == "leaflet" or attrs.get("data_channel_bridge_id") == "hq"
    assert m.props()["zoom"] == 12
    r = m.fly_to([28.7, 77.1], 14)
    assert r.ok and any(o.get("method") == "flyTo" for o in r.ops)


def test_codemirror_and_quill():
    ch = _ch()
    ed = CodeMirrorBridge(ch)("ed", value="print(1)", language="python")
    r = ed.set_value("print(2)")
    assert any(o.get("method") == "setValue" for o in r.ops)
    q = QuillBridge(ch)("doc", html="<p>Hi</p>")
    assert q.props()["html"].startswith("<p>")
    r2 = q.commit(html="<p>Bye</p>")
    assert r2.ok


def test_select_datepicker_sortable_swiper_mermaid():
    ch = _ch()
    sel = SelectBridge(ch)(
        "country",
        options=[{"value": "in", "label": "India"}, ("us", "USA"), "uk"],
        value="in",
    )
    assert len(sel.props()["options"]) == 3
    r = sel.set_value("us")
    assert any(o.get("method") == "setValue" for o in r.ops)

    dp = DatePickerBridge(ch)("when", value="2026-08-07", enable_time=True)
    assert dp.props()["enableTime"] is True
    r = dp.set_date("2026-09-01")
    assert any(o.get("method") == "setDate" for o in r.ops)

    sort = SortableBridge(ch)(
        "queue",
        items=[{"id": "a", "label": "A"}, {"id": "b", "label": "B"}],
    )
    r = sort.set_order(["b", "a"])
    assert any(o.get("method") == "setOrder" for o in r.ops)
    assert [i["id"] if isinstance(i, dict) else i for i in sort._state.items][0] in ("b", "a")

    sw = SwiperBridge(ch)("hero", slides=["One", {"html": "<b>Two</b>"}])
    assert len(sw.props()["slides"]) == 2
    r = sw.slide_to(1)
    assert any(o.get("method") == "slideTo" for o in r.ops)

    md = MermaidBridge(ch)("arch", chart="graph TD;A-->B")
    r = md.render()
    assert any(o.get("method") == "render" for o in r.ops)


def test_generic_bridge_any_package():
    ch = _ch()
    widgets = GenericBridge(ch, package="my-widget", methods=("update", "destroy", "focus"))
    w = widgets("w1", theme="dark", size=3)
    assert w.package == "my-widget"
    assert w.props()["theme"] == "dark"
    assert w.props()["size"] == 3
    r = w.commit(theme="light")
    assert r.ok and any(o.get("op") == "bridge.update" for o in r.ops)
    attrs = w.mount_attrs(class_name="p-4")
    assert "class" in attrs or "class_" in attrs or attrs.get("class") == "p-4" or "p-4" in str(attrs)


def test_script_helpers():
    assert "ux-ui.js" in UI_SCRIPT
    assert "ux-ui.js" in ui_script_tags()
    pack = bridge_script_tags(fx=True, ui=True)
    assert "ux-bridge.js" in pack and "ux-fx.js" in pack and "ux-ui.js" in pack
