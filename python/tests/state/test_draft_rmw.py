"""Draft / StateStore concurrency — get/set gap, edit, change, merge."""

from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor

import pytest

from ux_channel import Channel, StateConflict
from ux_channel.state import MemoryStateStore

SECRET = "dev-secret-key-32chars-minimum!!!!"


def test_get_set_pair_is_racy_under_interleaving():
    store = MemoryStateStore()

    def inc(_: int) -> None:
        n = int(store.get("n", 0) or 0)
        time.sleep(0.0002)
        store.set("n", n + 1)

    with ThreadPoolExecutor(32) as ex:
        list(ex.map(inc, range(200)))
    assert int(store.get("n", 0) or 0) < 200


def test_change_atomic_under_concurrency():
    store = MemoryStateStore()

    def inc(_: int) -> None:
        store.change("n", lambda n: (n or 0) + 1, default=0)

    with ThreadPoolExecutor(64) as ex:
        list(ex.map(inc, range(2000)))
    assert store.get("n") == 2000


def test_edit_context_manager_cas_commit():
    store = MemoryStateStore()
    with store.edit("n", default=0) as slot:
        slot.value += 1
    assert store.get("n") == 1
    with store.edit("n", default=0) as slot:
        slot.value += 5
    assert store.get("n") == 6


def test_edit_conflict_when_concurrent_writer():
    store = MemoryStateStore()
    store.set("n", 0)
    slot = store.edit("n", default=0)
    # external write bumps version
    store.set("n", 99)
    slot.value = 1
    with pytest.raises(StateConflict):
        slot.__exit__(None, None, None)


def test_edit_concurrent_increments_usually_win_or_conflict():
    """Under edit+CAS, either all commits succeed serially or conflicts surface."""
    store = MemoryStateStore()
    conflicts = []

    def inc(_: int) -> None:
        for _attempt in range(64):
            try:
                with store.edit("n", default=0) as slot:
                    slot.value = int(slot.value or 0) + 1
                return
            except StateConflict:
                conflicts.append(1)
                continue
        raise RuntimeError("too many conflicts")

    with ThreadPoolExecutor(32) as ex:
        list(ex.map(inc, range(300)))
    assert store.get("n") == 300


def test_draft_edit_and_merge():
    ch = Channel.boot(secret=SECRET)
    with ch.draft.edit("n", default=0) as slot:
        slot.value += 10
    assert ch.draft.get("n") == 10
    ch.draft.merge("form", email="a@b.c")
    ch.draft.merge("form", name="Ada")
    assert ch.draft.get("form") == {"email": "a@b.c", "name": "Ada"}


def test_update_and_patch_aliases():
    store = MemoryStateStore()
    store.update("n", lambda n: (n or 0) + 1, default=0)
    store.patch("f", {"a": 1}, default={})
    assert store.get("n") == 1
    assert store.get("f") == {"a": 1}


def test_incr_is_sugar():
    store = MemoryStateStore()
    assert store.incr("n") == 1
    assert store.incr("n", 2) == 3


import asyncio


def test_async_with_edit():
    store = MemoryStateStore()

    async def run():
        async with store.edit("n", default=0) as slot:
            slot.value += 3
        async with store.edit("n", default=0) as slot:
            slot.value += 2
        return store.get("n")

    assert asyncio.run(run()) == 5


def test_draft_async_with_edit_in_action():
    from ux_channel import Intent

    ch = Channel.boot(secret=SECRET)

    @ch.on(name="A.bump")
    async def bump():
        async with ch.draft.edit("n", default=0) as slot:
            slot.value += 1
        return ch.done(notice=str(ch.draft.get("n")))

    r = ch.registry.dispatch(Intent(action="A.bump", args={}, cap=ch.mint("A.bump", {})))
    assert r.ok
    assert ch.draft.get("n") == 1
    r = ch.registry.dispatch(Intent(action="A.bump", args={}, cap=ch.mint("A.bump", {})))
    assert ch.draft.get("n") == 2
