"""Channel dispatch / async_dispatch — same law as cek-python 0.1.3."""

from __future__ import annotations

import asyncio

from ux_channel.host.registry import ActionRegistry
from ux_channel.protocol.types import Intent, Result


SECRET = "async-dispatch-secret-32chars-min!!"


def _reg() -> ActionRegistry:
    return ActionRegistry(secret=SECRET, require_cap=False)


def test_sync_handler_sync_dispatch():
    reg = _reg()

    @reg.action("ping")
    def ping():
        return Result.success()

    assert reg.dispatch(Intent(action="ping")).ok


def test_async_handler_async_dispatch():
    reg = _reg()

    @reg.action("ping")
    async def ping():
        await asyncio.sleep(0)
        return Result.success()

    r = asyncio.run(reg.async_dispatch(Intent(action="ping")))
    assert r.ok


def test_sync_dispatch_refuses_async_handler():
    reg = _reg()

    @reg.action("ping")
    async def ping():
        return Result.success()

    try:
        reg.dispatch(Intent(action="ping"))
        raise AssertionError("sync dispatch must not run async handlers")
    except TypeError as e:
        assert "async_dispatch" in str(e)


def test_async_dispatch_runs_sync_handler():
    reg = _reg()

    @reg.action("ping")
    def ping():
        return Result.success()

    assert asyncio.run(reg.async_dispatch(Intent(action="ping"))).ok


def test_dispatch_async_is_alias():
    assert ActionRegistry.dispatch_async is ActionRegistry.async_dispatch
