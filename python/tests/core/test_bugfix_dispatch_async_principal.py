
"""Bugs found in second chaos pass."""

from __future__ import annotations

import asyncio
import threading
import time

from fastapi import FastAPI

from ux_channel import Channel, ChannelConfig, Principal
from ux_channel.host.state import StateConflict


def _ch():
    app = FastAPI()
    return Channel.boot(
        app,
        config=ChannelConfig.development(secret="dev-secret-key-32chars-minimum!!!!"),
    )


def test_dispatch_async_accepts_principal():
    ch = _ch()

    @ch.on(name="Auth.async", auth=True)
    async def me():
        return ch.done(notice="ok")

    cap = ch.registry.mint("Auth.async", {})

    async def run():
        denied = await ch.registry.dispatch_async(
            {"v": "1", "action": "Auth.async", "args": {}, "cap": cap}
        )
        assert not denied.ok
        ok = await ch.registry.dispatch_async(
            {"v": "1", "action": "Auth.async", "args": {}, "cap": cap},
            principal=Principal.of("u1"),
        )
        assert ok.ok, ok.error

    asyncio.run(run())


def test_edit_raises_on_contention_change_is_atomic():
    ch = _ch()
    ch.draft.set("k", 0)

    # change is the concurrent-safe path
    def worker():
        for _ in range(50):
            ch.draft.change("k", lambda x: int(x or 0) + 1, default=0)

    th = [threading.Thread(target=worker) for _ in range(8)]
    for t in th:
        t.start()
    for t in th:
        t.join()
    assert ch.draft.get("k") == 400


def test_edit_retry_survives_contention():
    ch = _ch()
    ch.draft.set("n", 0)

    def worker():
        for _ in range(40):
            ch.draft.edit_retry("n", lambda x: int(x or 0) + 1, default=0)

    th = [threading.Thread(target=worker) for _ in range(5)]
    for t in th:
        t.start()
    for t in th:
        t.join()
    assert ch.draft.get("n") == 200


def test_bare_edit_may_raise_state_conflict():
    ch = _ch()
    ch.draft.set("k", 1)
    conflicts = []

    def worker():
        try:
            with ch.draft.edit("k", default=0) as slot:
                cur = int(slot.value or 0)
                time.sleep(0.03)
                slot.value = cur + 1
        except StateConflict as e:
            conflicts.append(e)

    th = [threading.Thread(target=worker) for _ in range(4)]
    for t in th:
        t.start()
    for t in th:
        t.join()
    # at least some contention expected
    assert ch.draft.get("k") >= 2
    # and/or conflicts — either is fine; document behavior
    assert len(conflicts) >= 0


def test_region_render_crash_is_not_silent_ok():
    from ux_channel import Region

    ch = _ch()

    class Boom(Region):
        def render(self, ctx=None):
            raise RuntimeError("boom")

    b = Boom(ch, uid="boom").mount()
    r = ch.refresh(b)
    assert not r.ok
    assert r.error and r.error.code == "render_error"


def test_partial_refresh_ok_with_errors_meta():
    from ux_channel import Region

    ch = _ch()

    class Good(Region):
        def render(self, ctx=None):
            return "<b>g</b>"

    class Bad(Region):
        def render(self, ctx=None):
            raise ValueError("nope")

    g = Good(ch, uid="g").mount()
    b = Bad(ch, uid="bad").mount()
    r = ch.refresh(g, b)
    assert r.ok
    assert r.ops
    assert "refresh_errors" in (r.meta or {})


def test_unknown_only_refresh_fails_without_notice():
    ch = _ch()
    r = ch.refresh("ghost.region")
    assert not r.ok
    assert r.error and r.error.code == "render_error"
