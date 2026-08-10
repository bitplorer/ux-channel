"""ssr_state — public API, namespace isolation, power."""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from ux_channel import Channel, ChannelConfig, Intent, ssr_state


def _boot():
    app = FastAPI()
    ch = Channel.boot(
        app,
        config=ChannelConfig.development(
            secret="x" * 40, allow_memory_stores=True, require_cap=False
        ),
    )
    return app, ch, ssr_state(ch)


def test_public_api_session():
    _, ch, ui = _boot()
    n = ui.session("n", 0)

    @ui.region("badge")
    def badge(ctx):
        return f"<b>{n()}</b>"

    ui.paint("badge", wrap=False)

    @ui.action
    def inc():
        n.add(1)

    r = ch.registry.dispatch(Intent(action="inc", args={}, cap=ch.mint("inc", {})))
    assert any("1" in (o.get("html") or "") for o in r.ops)


def test_namespace_pattern_isolated_counters():
    _, ch, ui = _boot()
    locals_ = []
    for i in range(80):
        row = ui.namespace("line", i)
        q = row.session("qty", 0)  # default feed → row.uid
        locals_.append(q)

        @row.region
        def view(ctx, _q=q):
            return f"<span>{_q()}</span>"

    locals_[3].add(9)
    locals_[50].add(1)
    r = ui.done()
    morphs = [o for o in r.ops if o.get("op") == "morph"]
    assert len(morphs) <= 4
    assert locals_[0].peek() == 0
    assert locals_[3].peek() == 9
    assert locals_[50].peek() == 1
    assert locals_[3].key == "line:3:qty"


def test_namespace_region_paint_and_nest():
    _, ch, ui = _boot()
    row = ui.namespace("card", "abc")
    title = row.session("title", "hi", feed=False)
    meta = row.namespace("meta").session("flag", False)

    @row.region
    def view(ctx):
        return f"{title.peek()}:{meta.peek()}"

    html = row.paint(wrap=False)
    assert "hi" in html
    meta.toggle()
    assert meta.peek() is True


def test_shared_global_key():
    _, _, ui = _boot()
    assert ui.session("x", 1) is ui.session("x", 1)


def test_defensive_keys():
    _, _, ui = _boot()
    with pytest.raises(ValueError):
        ui.session("")
    with pytest.raises(ValueError):
        ui.namespace("line", None)
    with pytest.raises(ValueError):
        ui.namespace("line", "a/../b")


def test_changes_and_map():
    _, _, ui = _boot()
    a = ui.session("a", 0, refresh="ra")
    b = ui.session("b", 0, refresh="rb")

    @ui.region("ra")
    def ra(ctx):
        return str(a.peek())

    @ui.region("rb")
    def rb(ctx):
        return str(b.peek())

    with ui.changes():
        a.add(1)
        b.map(lambda x: (x or 0) + 4)
    assert a.peek() == 1 and b.peek() == 4


def test_http():
    app, ch, ui = _boot()
    n = ui.session("n", 0, refresh="c")

    @ui.region("c")
    def c(ctx):
        return f"<i>{n()}</i>"

    @ui.action
    def add():
        n.add(1)

    assert TestClient(app).post("/ux-channel/action", json={"action": "add", "args": {}}).json()["ok"]


def test_describe():
    _, _, ui = _boot()
    d = ui.describe()
    assert "namespace" in d["many"][0]
    assert "item" not in str(d).lower() or "namespace" in d["many"][0]
