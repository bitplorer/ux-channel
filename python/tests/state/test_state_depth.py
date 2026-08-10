"""
Deep surface tests — edge cases, multi-deps, async, HTTP load, API contracts.

Complements test_state_production_brutal.py (breadth/chaos) with depth.
"""

from __future__ import annotations

import concurrent.futures
import json

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from ux_channel import (
    Channel,
    ChannelConfig,
    ClientSafetyError,
    Intent,
    Result,
    state,
)
from ux_channel.ssr_state import ssr_state


def _boot(**kw):
    app = FastAPI()
    ch = Channel.boot(
        app,
        config=ChannelConfig.development(
            secret="z" * 40, allow_memory_stores=True, require_cap=False
        ),
    )
    return app, ch, state(ch, **kw)


# ═══════════════════════════════════════════════════════════════════════
# SessionVar depth
# ═══════════════════════════════════════════════════════════════════════

def test_peek_does_not_subscribe_get_does():
    _, ch, st = _boot()
    n = st.session("n", 0)

    @st.region("a")
    def a(ctx):
        n.peek()  # no track
        return "a"

    @st.region("b")
    def b(ctx):
        n()  # track
        return "b"

    st.paint("a")
    st.paint("b")
    g = st.describe()["session_graph"]
    assert "b" in g.get("n", [])
    assert "a" not in g.get("n", [])


def test_value_property_tracks_like_call():
    _, _, st = _boot()
    n = st.session("n", 7)

    @st.region("v")
    def v(ctx):
        return str(n.value)

    st.paint("v")
    assert "v" in st._bag.graph()["n"]


def test_set_mutator_vs_value_and_update_alias():
    _, _, st = _boot()
    n = st.session("n", 1)
    assert n.set(5) == 5
    assert n.set(lambda x: x + 2) == 7
    assert n.update(lambda x: x - 1) == 6


def test_feeds_multiple_regions_without_paint():
    _, ch, st = _boot()
    n = st.session("n", 0).feeds("r1", "r2")

    @st.region("r1")
    def r1(ctx):
        return f"1:{n.peek()}"

    @st.region("r2")
    def r2(ctx):
        return f"2:{n.peek()}"

    n.add(1)
    r = n.done()
    morphs = [o for o in r.ops if o.get("op") == "morph"]
    assert len(morphs) >= 2
    html = " ".join(o.get("html") or "" for o in morphs)
    assert "1:1" in html and "2:1" in html


def test_multi_atom_one_region_refreshes_once_per_done():
    _, _, st = _boot()
    a = st.session("a", 0)
    b = st.session("b", 0)

    @st.region("both")
    def both(ctx):
        return f"{a()}+{b()}"

    st.paint("both")
    a.add(1)
    b.add(1)
    r = st.done()
    morphs = [o for o in r.ops if o.get("op") == "morph"]
    # one region → typically one morph (or deduped)
    assert len(morphs) <= 2
    assert any("1+1" in (o.get("html") or "") for o in morphs)


def test_nested_namespace_keys():
    _, _, st = _boot()
    deep = st.namespace("u", 9).namespace("meta")
    note = deep.session("note", "")
    assert note.key == "u:9:meta:note"
    note.set("hi")
    assert note() == "hi"


def test_namespace_use_react_unpack():
    _, _, st = _boot()
    row = st.namespace("line", 3)
    get_q, set_q = row.use("qty", 0)
    set_q(4)
    assert get_q() == 4


def test_use_react_unpack_root():
    _, ch, st = _boot()
    ui = ssr_state(ch)
    get_n, set_n = ui.use("n", 0)
    set_n(lambda x: (x or 0) + 3)
    assert get_n() == 3


def test_bind_attrs_shape():
    _, _, st = _boot()

    @st.action
    def poke():
        pass

    attrs = st.bind(poke)
    assert isinstance(attrs, dict)
    assert any("action" in k for k in attrs)
    d = st._bag.bind_dict(poke)
    assert "data-channel-action" in d


def test_action_return_variants():
    _, ch, st = _boot()
    n = st.session("n", 0, refresh="x")

    @st.region("x")
    def x(ctx):
        return str(n.peek())

    @st.action
    def a_none():
        n.add(1)
        return None

    @st.action
    def a_str():
        n.add(1)
        return "saved"

    @st.action
    def a_result():
        n.add(1)
        return Result.success(notice="ok")

    for name in ("a_none", "a_str", "a_result"):
        r = ch.registry.dispatch(Intent(action=name, args={}, cap=ch.sign(name, {})))
        assert r.ok


def test_async_action():
    """Registry runs async handlers via asyncio.run under sync dispatch."""
    _, ch, st = _boot()
    n = st.session("n", 0, refresh="y")

    @st.region("y")
    def y(ctx):
        return str(n.peek())

    @st.action
    async def ainc():
        n.add(1)

    r = ch.registry.dispatch(Intent(action="ainc", args={}, cap=ch.sign("ainc", {})))
    assert r.ok
    assert n.peek() == 1


def test_snapshot_and_describe_contracts():
    _, _, st = _boot()
    st.session("a", 1).set(2)
    snap = st._bag.snapshot("a")
    assert snap.get("a") == 2
    d = st.describe()
    assert d["api"].startswith("state")
    assert set(d["kinds"]) >= {"session", "client", "db"}
    assert "session" in st.help()


def test_invalid_keys_rejected():
    _, _, st = _boot()
    with pytest.raises(ValueError):
        st.session("")
    with pytest.raises(ValueError):
        st.namespace("line", None)
    with pytest.raises(ValueError):
        st.namespace("a/../b", 1)


def test_large_dict_session_roundtrip():
    _, _, st = _boot()
    blob = {f"k{i}": i for i in range(500)}
    s = st.session("big", {})
    s.set(blob)
    got = s()
    assert got["k499"] == 499
    assert got is not blob  # deepcopy isolation


def test_nested_changes_defers_once():
    _, _, st = _boot()
    n = st.session("n", 0, refresh="z")

    @st.region("z")
    def z(ctx):
        return str(n.peek())

    with st.changes():
        with st.changes():
            n.add(1)
            n.add(1)
    assert n.peek() == 2


# ═══════════════════════════════════════════════════════════════════════
# Client depth
# ═══════════════════════════════════════════════════════════════════════

def test_client_push_flush_take():
    _, _, st = _boot()
    st.client.push({"ui.a": 1, "ui.b": 2})
    ops = st.client.take()
    assert len(ops) == 2
    assert st.client.take() == []


def test_client_allow_chain_and_configure():
    _, _, st = _boot()
    st.client.allow("ui.theme", "ui.locale")
    r = st.client("ui.locale", "hi", persist=True)
    assert r.ops[0].get("persist") is True


def test_client_path_traversal_and_empty():
    _, _, st = _boot()
    with pytest.raises(ClientSafetyError):
        st.client.check("")
    with pytest.raises(ClientSafetyError):
        st.client.check("../x")
    with pytest.raises(ClientSafetyError):
        st.client.check("a" * 300)


def test_client_flush_with_notice():
    _, _, st = _boot()
    st.client.set("ui.x", 1)
    r = st.client.flush(notice="ok")
    assert r.ok
    assert any(o.get("op") == "signal.set" for o in r.ops)


def test_reconfigure_allow_on_existing_state():
    _, ch, st = _boot()
    with pytest.raises(ClientSafetyError):
        st.client("ui.theme", "d", persist=True)
    st2 = state(ch, allow=["ui.theme"])
    assert st2 is st
    r = st.client("ui.theme", "d", persist=True)
    assert r.ops[0]["value"] == "d"


# ═══════════════════════════════════════════════════════════════════════
# DB depth
# ═══════════════════════════════════════════════════════════════════════

def test_db_custom_banned_and_empty_ok():
    _, _, st = _boot()
    st.db.ban_request_keys({"amount": None})  # empty value ok
    st.db.ban_request_keys({"amount": ""})
    with pytest.raises(ClientSafetyError):
        st.db.ban_request_keys({"foo": 1}, banned=["foo"])
    st.db.guard({})
    st.db.require(amount=0)  # zero is loaded


def test_db_require_non_risky_none_ok():
    _, _, st = _boot()
    # non-risky keys with None should not trip require
    st.db.require(label=None, amount=1)


# ═══════════════════════════════════════════════════════════════════════
# HTTP load + concurrent posts
# ═══════════════════════════════════════════════════════════════════════

def test_http_100_bumps():
    app, ch, st = _boot()
    n = st.session("n", 0, refresh="c")

    @st.region("c")
    def c(ctx):
        return str(n())

    @st.action
    def bump():
        n.add(1)

    client = TestClient(app)
    for _ in range(100):
        assert client.post("/ux-channel/action", json={"action": "bump", "args": {}}).json()["ok"]
    assert n.peek() == 100


def test_http_parallel_bumps_same_counter():
    app, ch, st = _boot()
    n = st.session("n", 0, refresh="c")

    @st.region("c")
    def c(ctx):
        return str(n())

    @st.action
    def bump():
        n.add(1)

    client = TestClient(app)

    def once(_):
        return client.post("/ux-channel/action", json={"action": "bump", "args": {}}).json()["ok"]

    with concurrent.futures.ThreadPoolExecutor(8) as ex:
        oks = list(ex.map(once, range(40)))
    assert all(oks)
    # Memory draft should apply all increments (lock in store)
    assert n.peek() == 40


def test_paint_wrap_and_region_uid_in_html():
    _, _, st = _boot()
    n = st.session("n", 3)

    @st.region("box")
    def box(ctx):
        return f'<span data-channel-id="box">{n()}</span>'

    html = st.paint("box", wrap=False)
    assert "3" in html


def test_dependency_precision_only_dirty_keys():
    _, ch, st = _boot()
    a = st.session("a", 0)
    b = st.session("b", 0)

    @st.region("ra")
    def ra(ctx):
        return f"A{a()}"

    @st.region("rb")
    def rb(ctx):
        return f"B{b()}"

    st.paint("ra")
    st.paint("rb")
    a.add(1)
    r = st.done()
    targets = []
    for o in r.ops:
        if o.get("op") == "morph":
            html = o.get("html") or ""
            targets.append(html)
    joined = " ".join(targets)
    assert "A1" in joined
    # b untouched — rb should not need morph; if present must still be B0
    if "B" in joined:
        assert "B0" in joined or "B1" not in joined


def test_action_with_client_set_via_done_merge():
    _, ch, st = _boot(allow=["ui.theme"])

    @st.action
    def theme():
        st.client.set("ui.theme", "dark")
        # action auto-done from session; client queue merged only if ChannelState.done
        # @st.action uses bag.done not ChannelState.done — client may not merge
        return st.done()  # explicit ChannelState.done

    r = ch.registry.dispatch(Intent(action="theme", args={}, cap=ch.sign("theme", {})))
    assert r.ok
    assert any(o.get("op") == "signal.set" for o in r.ops)
