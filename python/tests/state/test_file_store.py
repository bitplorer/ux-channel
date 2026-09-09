"""FileStateStore — JSON sqlite bag shared across two connections / processes."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from multiprocessing import get_context

import pytest

from ux_channel import Channel
from ux_channel.host.config import ChannelConfig
from ux_channel.host.stores import FileStateStore, MemoryStateStore, StateConflict

SECRET = "dev-secret-key-32chars-minimum!!!!"


def _boot(**kwargs):
    """Headless boot without Cap Host — these tests pin the store plane."""
    cfg = ChannelConfig.development(secret=SECRET, cek="off")
    return Channel.boot(config=cfg, **kwargs)


def _inc_in_child(path: str, n: int) -> None:
    """Spawn target: must be module-level for multiprocessing."""
    store = FileStateStore(path)
    try:
        for _ in range(n):
            store.change("n", lambda v: (v or 0) + 1, default=0)
    finally:
        store.close()


def test_two_file_stores_share_json_values(tmp_path):
    path = tmp_path / "draft.sqlite"
    writer = FileStateStore(path)
    reader = FileStateStore(path)
    try:
        writer.set("ui.hello.n", 10)
        assert reader.get("ui.hello.n", 0) == 10
    finally:
        writer.close()
        reader.close()


def test_file_store_change_visible_to_peer(tmp_path):
    path = tmp_path / "draft.sqlite"
    a = FileStateStore(path)
    b = FileStateStore(path)
    try:
        a.change("n", lambda v: (v or 0) + 1, default=0)
        a.change("n", lambda v: (v or 0) + 1, default=0)
        assert b.get("n", 0) == 2
    finally:
        a.close()
        b.close()


def test_file_store_clear_empties_peer(tmp_path):
    path = tmp_path / "draft.sqlite"
    a = FileStateStore(path)
    b = FileStateStore(path)
    try:
        a.set("k", "v")
        a.clear()
        assert b.get("k", None) is None
    finally:
        a.close()
        b.close()


def test_file_store_edit_cas(tmp_path):
    store = FileStateStore(tmp_path / "cas.sqlite")
    try:
        with store.edit("n", default=0) as slot:
            slot.value += 1
        assert store.get("n") == 1
        slot = store.edit("n", default=0)
        store.set("n", 99)
        slot.value = 1
        with pytest.raises(StateConflict):
            slot.__exit__(None, None, None)
    finally:
        store.close()


def test_file_store_change_atomic_under_concurrency(tmp_path):
    store = FileStateStore(tmp_path / "conc.sqlite")
    try:

        def inc(_: int) -> None:
            store.change("n", lambda n: (n or 0) + 1, default=0)

        with ThreadPoolExecutor(32) as ex:
            list(ex.map(inc, range(400)))
        assert store.get("n") == 400
    finally:
        store.close()


def test_file_store_change_atomic_across_processes(tmp_path):
    path = tmp_path / "mp.sqlite"
    bootstrap = FileStateStore(path)
    bootstrap.close()
    per = 40
    workers = 4
    ctx = get_context("spawn")
    procs = [
        ctx.Process(target=_inc_in_child, args=(str(path), per))
        for _ in range(workers)
    ]
    for p in procs:
        p.start()
    for p in procs:
        p.join(timeout=60)
        assert p.exitcode == 0, p.exitcode
    store = FileStateStore(path)
    try:
        assert store.get("n") == per * workers
    finally:
        store.close()


def test_file_store_is_json_not_pickle(tmp_path):
    path = tmp_path / "json.sqlite"
    store = FileStateStore(path)
    try:
        store.set("form", {"email": "a@b.c", "n": 3})
        row = store._conn.execute("SELECT v FROM kv WHERE k = ?", ("form",)).fetchone()
        assert row is not None
        raw = row[0]
        if isinstance(raw, bytes):
            raw = raw.decode("utf-8")
        assert "email" in raw
        assert "a@b.c" in raw
        assert raw.lstrip()[:1] in "{["
    finally:
        store.close()
    # After checkpoint, the main file is UTF-8 JSON, not pickle.
    disk = path.read_bytes()
    assert b"email" in disk
    assert b"\x80" not in disk


def test_json_roundtrip_keeps_json_domain(tmp_path):
    path = tmp_path / "types.sqlite"
    store = FileStateStore(path)
    other = FileStateStore(path)
    try:
        store.set("bag", {"n": 3, "ok": True, "xs": [1, 2], "name": "a"})
        v = other.get("bag")
        assert v == {"n": 3, "ok": True, "xs": [1, 2], "name": "a"}
        assert type(v["n"]) is int
        assert type(v["ok"]) is bool
    finally:
        store.close()
        other.close()


def test_file_store_merge_incr_delete_keys(tmp_path):
    store = FileStateStore(tmp_path / "sugar.sqlite")
    try:
        store.merge("form", {"email": "a@b.c"}, default={})
        store.merge("form", {"n": 1}, default={})
        assert store.get("form") == {"email": "a@b.c", "n": 1}
        assert store.incr("n") == 1
        assert store.incr("n", 2) == 3
        assert "form" in store.keys() and "n" in store.keys()
        store.delete("form")
        assert store.get("form") is None
        assert "form" not in store.keys()
    finally:
        store.close()


def test_file_store_edit_retry(tmp_path):
    store = FileStateStore(tmp_path / "retry.sqlite")
    try:
        out = store.edit_retry("n", lambda v: (v or 0) + 4, default=0)
        assert out == 4
        assert store.get("n") == 4
    finally:
        store.close()


def test_boot_honors_uxcompose_state_store(tmp_path, monkeypatch):
    path = tmp_path / "boot.sqlite"
    monkeypatch.setenv("UXCOMPOSE_STATE_STORE", str(path))
    monkeypatch.delenv("REDIS_URL", raising=False)
    ch = _boot()
    assert isinstance(ch.state, FileStateStore)
    ch.state.set("n", 4)
    other = _boot()
    assert other.state.get("n") == 4
    ch.state.close()
    other.state.close()


def test_boot_without_env_stays_memory(monkeypatch):
    monkeypatch.delenv("UXCOMPOSE_STATE_STORE", raising=False)
    monkeypatch.delenv("REDIS_URL", raising=False)
    ch = _boot()
    assert isinstance(ch.state, MemoryStateStore)


def test_boot_explicit_state_wins_over_env(tmp_path, monkeypatch):
    monkeypatch.setenv("UXCOMPOSE_STATE_STORE", str(tmp_path / "ignored.sqlite"))
    monkeypatch.delenv("REDIS_URL", raising=False)
    mem = MemoryStateStore()
    ch = _boot(state=mem)
    assert ch.state is mem


def test_boot_redis_url_env_skips_file_store(tmp_path, monkeypatch):
    monkeypatch.setenv("UXCOMPOSE_STATE_STORE", str(tmp_path / "x.sqlite"))
    monkeypatch.setenv("REDIS_URL", "redis://127.0.0.1:1/0")
    ch = _boot()
    assert not isinstance(ch.state, FileStateStore)
