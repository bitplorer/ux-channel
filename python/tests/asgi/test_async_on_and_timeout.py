"""@ch.on async handlers must run; timeouts must fire."""

from __future__ import annotations

import asyncio
import inspect
import time

from ux_channel import Channel, Intent

SECRET = "dev-secret-key-32chars-minimum!!!!"


def test_async_on_handler_runs_and_returns_ops():
    ch = Channel.boot(secret=SECRET)

    @ch.on(name="A.ping")
    async def ping():
        await asyncio.sleep(0.01)
        return ch.done(notice="pong")

    assert inspect.iscoroutinefunction(ch.registry.get("A.ping"))
    r = ch.registry.dispatch(Intent(action="A.ping", args={}, cap=ch.mint("A.ping", {})))
    assert r.ok
    assert any(o.get("message") == "pong" for o in r.ops)


def test_async_timeout():
    ch = Channel.boot(secret=SECRET)
    ch.registry.action_timeout_s = 0.05

    @ch.on(name="A.slow")
    async def slow():
        await asyncio.sleep(0.5)
        return ch.done(notice="late")

    r = ch.registry.dispatch(Intent(action="A.slow", args={}, cap=ch.mint("A.slow", {})))
    assert not r.ok
    assert r.error and r.error.code == "timeout"


def test_sync_timeout():
    ch = Channel.boot(secret=SECRET)
    ch.registry.action_timeout_s = 0.05

    @ch.on(name="A.sslow")
    def slow():
        time.sleep(0.3)
        return ch.done(notice="late")

    r = ch.registry.dispatch(Intent(action="A.sslow", args={}, cap=ch.mint("A.sslow", {})))
    assert not r.ok
    assert r.error and r.error.code == "timeout"


def test_paint_failure_skips_region_keeps_others():
    ch = Channel.boot(secret=SECRET)

    @ch.region("bad")
    def bad(ctx):
        raise RuntimeError("paint boom")

    @ch.region("good")
    def good(ctx):
        return "GOOD"

    @ch.on(name="A.ref")
    def ref():
        return ch.done(refresh=["good", "bad"], notice="n")

    r = ch.registry.dispatch(Intent(action="A.ref", args={}, cap=ch.mint("A.ref", {})))
    assert r.ok
    assert any(o.get("op") == "morph" and "GOOD" in str(o.get("html")) for o in r.ops)
