"""An ``edit`` slot never commits over a key that was deleted and set again.

Versions come from one store-wide sequence, so delete + set cannot bring a
key back to a version a stale slot still holds.
"""

from __future__ import annotations

import sqlite3

import pytest

from ux_channel.host.stores import FileStateStore, MemoryStateStore, StateConflict


@pytest.fixture(params=["memory", "file"])
def store(request, tmp_path):
    if request.param == "memory":
        yield MemoryStateStore()
        return
    st = FileStateStore(tmp_path / "s.sqlite")
    yield st
    st.close()


def test_stale_edit_after_delete_and_set_conflicts(store):
    store.set("k", "A")
    slot = store.edit("k")
    slot.value = "stale"
    store.delete("k")
    store.set("k", "B")
    with pytest.raises(StateConflict):
        slot.__exit__(None, None, None)
    assert store.get("k") == "B"


def test_stale_edit_after_clear_and_set_conflicts(store):
    store.set("k", "A")
    slot = store.edit("k")
    slot.value = "stale"
    store.clear()
    store.change("k", lambda _: "B")
    with pytest.raises(StateConflict):
        slot.__exit__(None, None, None)
    assert store.get("k") == "B"


def test_file_stale_edit_conflicts_across_connections(tmp_path):
    path = tmp_path / "s.sqlite"
    editor, other = FileStateStore(path), FileStateStore(path)
    try:
        editor.set("k", "A")
        slot = editor.edit("k")
        slot.value = "stale"
        other.delete("k")
        other.set("k", "B")
        with pytest.raises(StateConflict):
            slot.__exit__(None, None, None)
        assert editor.get("k") == "B"
    finally:
        editor.close()
        other.close()


def test_file_sequence_starts_above_existing_versions(tmp_path):
    """A file written before the sequence table keeps its versions monotonic."""
    path = tmp_path / "old.sqlite"
    conn = sqlite3.connect(path)
    conn.execute("CREATE TABLE kv (k TEXT PRIMARY KEY NOT NULL, v TEXT NOT NULL, ver INTEGER NOT NULL)")
    conn.execute("INSERT INTO kv VALUES ('k', '\"A\"', 7)")
    conn.commit()
    conn.close()
    st = FileStateStore(path)
    try:
        slot = st.edit("k")
        slot.value = "edited"
        st.set("other", 1)
        slot.__exit__(None, None, None)
        assert st.get("k") == "edited"
        stale = st.edit("k")
        st.delete("k")
        st.set("k", "B")
        with pytest.raises(StateConflict):
            stale.__exit__(None, None, None)
    finally:
        st.close()
