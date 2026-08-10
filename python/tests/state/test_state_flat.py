"""Flat state(ch) — low-load DX."""

from __future__ import annotations

import pytest
from fastapi import FastAPI

from ux_channel import Channel, ChannelConfig, ClientSafetyError, Intent, state


def _boot(**kw):
    app = FastAPI()
    ch = Channel.boot(
        app,
        config=ChannelConfig.development(
            secret="x" * 40, allow_memory_stores=True, require_cap=False
        ),
    )
    return app, ch, state(ch, **kw)


def test_day1_session_region_action():
    _, ch, st = _boot()
    n = st.session("n", 0)

    @st.region("badge")
    def badge(ctx):
        return f"<b>{n()}</b>"

    st.paint("badge", wrap=False)

    @st.action
    def inc():
        n.add(1)

    r = ch.registry.dispatch(Intent(action="inc", args={}, cap=ch.sign("inc", {})))
    assert any("1" in (o.get("html") or "") for o in r.ops)
    assert ch.st is st


def test_namespace_call_sugar():
    _, _, st = _boot()
    row = st.namespace("line", 1)
    q = row("qty", 0)  # same as row.session
    assert q.key == "line:1:qty"


def test_client_call_and_allow():
    _, _, st = _boot(allow=["ui.theme"])
    r = st.client("ui.theme", "dark", persist=True)
    assert r.ops[0]["op"] == "signal.set"
    with pytest.raises(ClientSafetyError):
        st.client("pay.amount", 9)


def test_db_guard_require():
    _, _, st = _boot()
    st.db.guard({"sku": "a"})
    with pytest.raises(ClientSafetyError):
        st.db.guard({"amount": 1})
    st.db.require(amount=10)
    with pytest.raises(ClientSafetyError):
        st.db.require(amount=None)


def test_done_merges_client_queue():
    _, _, st = _boot()
    st.client.set("ui.sidebar", True)
    r = st.done()
    assert any(o.get("op") == "signal.set" for o in r.ops)


def test_help():
    _, _, st = _boot()
    assert "st.session" in st.help()
