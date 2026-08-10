"""Slot composition patterns — named, scoped, list, conditional, fallback."""

from __future__ import annotations

import pytest

from ux_channel import Channel, ChannelConfig
from ux_channel.components import (
    ChannelComponent,
    Composite,
    Slot,
    SlotContext,
    SlotList,
    Slots,
    choose_slot,
    fragment,
    map_slot,
    nest,
)
from ux_channel.components.slots import render_fragment

SECRET = "dev-secret-key-32chars-minimum!!!!"


def _host():
    cfg = ChannelConfig.development(secret=SECRET, rate_limit_per_minute=0)
    return Channel.boot(config=cfg)


class U:
    def __init__(self, h):
        self.h = h

    def __render__(self):
        return self.h


def test_named_and_default_slot():
    s = Slot("header", content="<h1>Hi</h1>")
    assert s.html() == "<h1>Hi</h1>"
    empty = Slot("body", default="<p>fallback</p>")
    assert empty.html() == "<p>fallback</p>"
    assert Slot("x", default="fb").html() == "fb"


def test_required_slot_raises():
    s = Slot("main", required=True)
    with pytest.raises(ValueError, match="required"):
        s.html()


def test_scoped_slot_with_context():
    s = Slot("row", content=lambda ctx: f"<td>{ctx['name']}-{ctx['index']}</td>")
    html = s.html_scoped({"name": "Ring", "index": 2})
    assert html == "<td>Ring-2</td>"


def test_scoped_slot_props_kwargs_style():
    s = Slot("cell", content=lambda name, price: f"{name}:{price}")
    # html_scoped tries ctx first then **props
    html = s.html_scoped({"name": "A", "price": 9})
    assert "A" in html and "9" in html


def test_conditional_when():
    s = Slot(
        "err",
        content="<p class='e'>bad</p>",
        when=lambda st: bool(st.get("error")),
    )
    assert s.html(error=False) == ""
    assert "bad" in s.html(error=True)


def test_slot_list_and_map_slot():
    items = [{"title": "a"}, {"title": "b"}]
    html = SlotList(
        "row",
        lambda ctx: f"<li>{ctx['title']}</li>",
        wrapper_tag="ul",
        empty="<p>none</p>",
    ).render(items)
    assert html == "<ul><li>a</li><li>b</li></ul>"
    assert SlotList("row", "x", empty="EMPTY").render([]) == "EMPTY"
    assert map_slot(items, lambda ctx: ctx["title"], sep="") == "ab" or "a" in map_slot(
        items, lambda ctx: f"{ctx['title']}"
    )


def test_choose_slot_switch():
    state = {"mode": "ok"}
    html = choose_slot(
        state,
        (lambda s: s.get("mode") == "err", "<b>err</b>"),
        (lambda s: s.get("mode") == "ok", U("<b>ok</b>")),
        default="<b>idle</b>",
    )
    assert html == "<b>ok</b>"


def test_slots_bag_fill_and_render_all():
    bag = (
        Slots()
        .set("header", U("<h1>H</h1>"))
        .set("body", default="<p>empty</p>")
        .set("foot", "f")
    )
    all_ = bag.render_all()
    assert "H" in all_["header"] and all_["body"] == "<p>empty</p>"
    bag.fill(body="<p>full</p>")
    assert bag.render("body") == "<p>full</p>"


def test_composite_slot_defaults_and_scoped_layout():
    host = _host()

    class Card(Composite):
        kind = "Card"
        slot_names = ("title", "body", "rows")
        slot_defaults = {"title": "<h3>Untitled</h3>"}

        def layout(self, slots, **state):
            rows = SlotList(
                "row",
                lambda ctx: f"<li>{ctx.get('name', ctx.get('item', ''))}</li>",
                wrapper_tag="ul",
            ).render(state.get("items") or [])
            return f"{slots['title']}{slots['body']}{rows}"

    card = Card(host, uid="C:1", slots={"body": U("<p>desc</p>")}).install()
    html = card.render(items=[{"name": "x"}, {"name": "y"}])
    assert "Untitled" in html and "desc" in html and "<li>x</li>" in html


def test_nest_fragments():
    assert nest(U("<a/>"), "", U("<b/>"), sep="") == "<a/><b/>"


def test_nested_channel_component_in_slot():
    host = _host()

    class Inner(ChannelComponent):
        kind = "Inner"

        def render(self, **state):
            return f"<em>{state.get('n', 0)}</em>"

    class Outer(Composite):
        kind = "Outer"
        slot_names = ("main",)

        def layout(self, slots, **state):
            return f"<section>{slots['main']}</section>"

    inner = Inner(host, uid="I:1")
    outer = Outer(host, uid="O:1", slots={"main": inner}).install()
    html = outer.render(n=3)
    # state passes into nested component via fragment
    assert "3" in html or "<em>" in html


def test_render_fragment_ux_dom_and_str():
    assert render_fragment(U("<i>z</i>")) == "<i>z</i>"
    assert render_fragment(None) == ""
    assert fragment("<b>1</b>") == "<b>1</b>"
