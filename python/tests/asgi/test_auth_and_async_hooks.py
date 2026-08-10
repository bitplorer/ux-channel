"""auth=True must see dispatch(principal=); async hooks work on sync dispatch."""

from __future__ import annotations

import asyncio

from ux_channel import Channel, Intent, Principal, Result

SECRET = "dev-secret-key-32chars-minimum!!!!"


def test_auth_true_accepts_dispatch_principal():
    ch = Channel.boot(secret=SECRET)

    @ch.on(name="Sec.x", auth=True)
    async def sec():
        return ch.done(notice="ok")

    r = ch.registry.dispatch(Intent(action="Sec.x", args={}, cap=ch.mint("Sec.x", {})))
    assert not r.ok and r.error and r.error.code == "unauthorized"

    r = ch.registry.dispatch(
        Intent(action="Sec.x", args={}, cap=ch.mint("Sec.x", {})),
        principal=Principal.of("user-1"),
    )
    assert r.ok


def test_async_before_hook_on_sync_dispatch():
    ch = Channel.boot(secret=SECRET)

    @ch.before
    async def deny(intent, args):
        if intent.action == "H.block":
            return Result.failure("forbidden", "blocked")
        return None

    @ch.on(name="H.block")
    def block():
        return ch.done(notice="nope")

    r = ch.registry.dispatch(
        Intent(action="H.block", args={}, cap=ch.mint("H.block", {}))
    )
    assert not r.ok
    assert r.error and r.error.code == "forbidden"


def test_async_after_hook_on_sync_dispatch():
    ch = Channel.boot(secret=SECRET)
    seen = []

    @ch.after
    async def mark(intent, result):
        seen.append(intent.action)
        return result

    @ch.on(name="H.ok")
    def ok():
        return ch.done(notice="y")

    r = ch.registry.dispatch(Intent(action="H.ok", args={}, cap=ch.mint("H.ok", {})))
    assert r.ok
    assert seen == ["H.ok"]
