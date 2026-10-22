"""Session values are per visitor: keyed by the verified Cap subject.

Without a subject a read returns the default and a write raises.
``reading_as`` binds a page paint's reads. ``shared`` is one app-wide cell.
"""

from __future__ import annotations

import pytest

from ux_channel import Channel, ChannelConfig, Intent, Principal, state
from ux_channel.host.ssr_state import NoSessionSubject, reading_as

from helpers.channel import as_visitor


def _boot():
    ch = Channel.boot(
        config=ChannelConfig.development(secret="s" * 40, allow_memory_stores=True)
    )
    return ch, state(ch)


def _as_caller(ch, subject):
    ch.registry.auth_resolver = lambda request: Principal(id=subject)


def test_two_subjects_have_independent_values():
    _, st = _boot()
    n = st.session("n", 0)
    with as_visitor("alice"):
        n.add(5)
    with as_visitor("bob"):
        assert n() == 0
        n.add(1)
    with as_visitor("alice"):
        assert n() == 5
    with as_visitor("bob"):
        assert n() == 1


def test_no_subject_reads_default_and_refuses_writes():
    _, st = _boot()
    n = st.session("n", 7)
    with as_visitor("alice"):
        n.set(1)
    assert n() == 7
    assert n.peek() == 7
    for write in (lambda: n.set(2), lambda: n.add(1), n.toggle, n.reset, lambda: n.merge(a=1)):
        with pytest.raises(NoSessionSubject):
            write()
    with as_visitor("alice"):
        assert n() == 1


def test_namespace_values_are_per_subject():
    _, st = _boot()
    qty = st.namespace("line", 3).session("qty", 0)
    with as_visitor("alice"):
        qty.add(2)
    with as_visitor("bob"):
        assert qty() == 0


def test_shared_is_one_value_for_everyone():
    _, st = _boot()
    hits = st.shared("hits", 0)
    with as_visitor("alice"):
        hits.add(1)
    with as_visitor("bob"):
        hits.add(1)
    hits.add(1)
    assert hits() == 3
    assert st.session("hits", 0) is not hits


def test_shared_and_session_cells_of_one_name_are_separate():
    _, st = _boot()
    with as_visitor("alice"):
        st.session("n", 0).set(1)
        st.shared("n", 0).set(9)
        assert st.session("n", 0)() == 1
    assert st.shared("n", 0)() == 9
    # A key with "/" could spell a session store key, so it is refused.
    with pytest.raises(ValueError):
        st.shared("@alice/n:x", 0)()


def test_reading_as_paints_that_subjects_values_and_cannot_write():
    _, st = _boot()
    n = st.session("n", 0)
    with as_visitor("alice"):
        n.set(4)
    with reading_as("alice"):
        assert n() == 4
        with pytest.raises(NoSessionSubject):
            n.add(1)
    with reading_as("bob"):
        assert n() == 0


def test_dispatch_keys_by_the_cap_subject():
    ch, st = _boot()
    n = st.session("n", 0)

    @st.action
    def bump():
        n.add(1)

    @st.action
    def peek():
        return f"n={n()}"

    _as_caller(ch, "alice")
    for _ in range(2):
        r = ch.registry.dispatch(Intent(action="bump", args={}, cap=ch.mint("bump", {}, sub="alice")))
        assert r.ok, r
    _as_caller(ch, "bob")
    r = ch.registry.dispatch(Intent(action="bump", args={}, cap=ch.mint("bump", {}, sub="bob")))
    assert r.ok, r

    with as_visitor("alice"):
        assert n() == 2
    with as_visitor("bob"):
        assert n() == 1


def test_dispatch_without_cap_subject_cannot_write_session():
    ch, st = _boot()
    n = st.session("n", 0)

    @st.action
    def bump():
        n.add(1)

    r = ch.registry.dispatch(Intent(action="bump", args={}, cap=ch.mint("bump", {})))
    assert not r.ok
    assert r.error.code == "internal"
    with reading_as("anyone"):
        assert n() == 0
