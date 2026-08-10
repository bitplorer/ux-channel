"""First-class parallel / concurrent dispatch for ux-channel — day-1 guarantees."""

from __future__ import annotations

import asyncio
import threading
import unittest

from ux_channel.transport.concurrency import (
    default_workers,
    dispatch_parallel,
    dispatch_parallel_async,
    install_bulkhead,
    map_dispatch,
)
from ux_channel.host.context import Principal
from ux_channel.host.registry import ActionRegistry
from ux_channel.protocol.types import Intent, Result


def _reg(*, require_cap: bool = False) -> ActionRegistry:
    return ActionRegistry(
        secret="test-secret-key-32chars-minimum!!!!",
        require_cap=require_cap,
    )


class TestParallelDispatch(unittest.TestCase):
    def test_default_workers(self):
        w = default_workers()
        self.assertGreaterEqual(w, 2)
        self.assertLessEqual(w, 32)

    def test_dispatch_parallel_all_ok(self):
        reg = _reg()

        @reg.action("echo")
        def echo(ctx, n: int = 0):
            return Result.success(n=n)

        intents = [
            Intent(action="echo", args={"n": i}, request_id=f"r{i}") for i in range(30)
        ]
        results = dispatch_parallel(reg, intents, max_workers=8)
        self.assertEqual(len(results), 30)
        self.assertTrue(all(r.ok for r in results))
        self.assertEqual([r.meta.get("n") for r in results], list(range(30)))

    def test_dispatch_parallel_isolates_failures(self):
        reg = _reg()

        @reg.action("maybe")
        def maybe(ctx, n: int = 0):
            if n % 2:
                return Result.failure("bad_request", f"odd {n}")
            return Result.success(n=n)

        intents = [
            Intent(action="maybe", args={"n": i}, request_id=f"m{i}") for i in range(20)
        ]
        results = dispatch_parallel(reg, intents, max_workers=6)
        self.assertEqual(sum(1 for r in results if r.ok), 10)
        self.assertEqual(sum(1 for r in results if not r.ok), 10)

    def test_map_dispatch(self):
        reg = _reg()

        @reg.action("add1")
        def add1(ctx, x: int = 0):
            return Result.success(y=x + 1)

        results = map_dispatch(
            reg, "add1", [{"x": i} for i in range(15)], max_workers=4
        )
        self.assertEqual([r.meta.get("y") for r in results], list(range(1, 16)))

    def test_async_parallel(self):
        reg = _reg()

        @reg.action("ping")
        async def ping(ctx, n: int = 0):
            await asyncio.sleep(0)
            return Result.success(n=n)

        intents = [
            Intent(action="ping", args={"n": i}, request_id=f"a{i}") for i in range(25)
        ]

        async def run():
            return await dispatch_parallel_async(reg, intents, limit=8)

        results = asyncio.run(run())
        self.assertEqual(len(results), 25)
        self.assertTrue(all(r.ok for r in results))

    def test_bulkhead_rejects_excess(self):
        reg = _reg()
        lim = install_bulkhead(reg, max_in_flight=2)
        gate = threading.Barrier(3)  # 2 workers + main? use Event instead
        release = threading.Event()
        started = threading.Semaphore(0)

        @reg.action("block")
        def block(ctx):
            started.release()
            release.wait(timeout=3)
            return Result.success()

        def hold(rid: str):
            reg.dispatch(Intent(action="block", args={}, request_id=rid))

        t1 = threading.Thread(target=hold, args=("h1",))
        t2 = threading.Thread(target=hold, args=("h2",))
        t1.start()
        t2.start()
        # wait until both handlers entered
        self.assertTrue(started.acquire(timeout=2))
        self.assertTrue(started.acquire(timeout=2))
        r = reg.dispatch(Intent(action="block", args={}, request_id="x"))
        self.assertFalse(r.ok)
        self.assertEqual(r.error.code, "rate_limited")
        release.set()
        t1.join(timeout=3)
        t2.join(timeout=3)
        stats = lim.stats()
        self.assertGreaterEqual(stats["rejected"], 1)
        self.assertGreaterEqual(stats["accepted"], 2)

    def test_channel_facade_methods(self):
        from ux_channel import Channel

        reg = _reg()

        @reg.action("z")
        def z(ctx, n: int = 0):
            return Result.success(n=n)

        ch = Channel.from_registry(reg)
        intents = [
            Intent(action="z", args={"n": i}, request_id=f"z{i}") for i in range(10)
        ]
        results = ch.dispatch_parallel(intents, max_workers=4)
        self.assertTrue(all(r.ok for r in results))

        async def run():
            return await ch.dispatch_parallel_async(intents, limit=4)

        results2 = asyncio.run(run())
        self.assertTrue(all(r.ok for r in results2))

        mapped = ch.map_dispatch("z", [{"n": 1}, {"n": 2}])
        self.assertEqual([r.meta.get("n") for r in mapped], [1, 2])

    def test_principal_override_parallel(self):
        reg = _reg()

        @reg.action("who")
        def who(ctx):
            pid = getattr(ctx.principal, "id", None) if ctx.principal else None
            return Result.success(id=pid)

        p = Principal.of("user-7")
        intents = [
            Intent(action="who", args={}, request_id=f"w{i}") for i in range(8)
        ]
        results = dispatch_parallel(reg, intents, max_workers=4, principal=p)
        self.assertTrue(all(r.ok for r in results))
        self.assertTrue(all(r.meta.get("id") == "user-7" for r in results))


if __name__ == "__main__":
    unittest.main()
