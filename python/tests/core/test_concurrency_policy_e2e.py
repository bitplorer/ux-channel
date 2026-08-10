"""E2E: concurrency policy opt-in/opt-out with sensible defaults (ux-channel)."""

from __future__ import annotations

import asyncio
import os
import unittest

from ux_channel.transport.batch import dispatch_batch, dispatch_batch_async
from ux_channel.transport.concurrency import (
    configure_concurrency,
    dispatch_parallel,
    dispatch_parallel_async,
    get_concurrency_settings,
    map_dispatch,
    reset_concurrency_settings,
    should_parallelize,
)
from ux_channel.host.registry import ActionRegistry
from ux_channel.protocol.types import Intent, Result


def _reg() -> ActionRegistry:
    return ActionRegistry(
        secret="test-secret-key-32chars-minimum!!!!",
        require_cap=False,
    )


class TestPolicyDefaults(unittest.TestCase):
    def tearDown(self):
        reset_concurrency_settings()

    def test_defaults(self):
        reset_concurrency_settings()
        s = get_concurrency_settings()
        self.assertTrue(s.parallel_enabled)
        self.assertFalse(s.batch_parallel)  # batch stays sequential by default
        self.assertEqual(s.min_items_for_parallel, 2)
        self.assertIsNone(s.max_in_flight)  # bulkhead opt-in


class TestDispatchParallelPolicy(unittest.TestCase):
    def tearDown(self):
        reset_concurrency_settings()

    def test_opt_out_same_results(self):
        reg = _reg()

        @reg.action("echo")
        def echo(ctx, n: int = 0):
            return Result.success(n=n)

        intents = [
            Intent(action="echo", args={"n": i}, request_id=f"r{i}") for i in range(20)
        ]
        configure_concurrency(parallel_enabled=True)
        a = dispatch_parallel(reg, intents, max_workers=6)
        configure_concurrency(parallel_enabled=False)
        b = dispatch_parallel(reg, intents)
        self.assertEqual([r.meta.get("n") for r in a], [r.meta.get("n") for r in b])
        self.assertTrue(all(r.ok for r in a + b))

    def test_call_level_overrides(self):
        reg = _reg()

        @reg.action("echo")
        def echo(ctx, n: int = 0):
            return Result.success(n=n)

        intents = [
            Intent(action="echo", args={"n": i}, request_id=f"c{i}") for i in range(10)
        ]
        configure_concurrency(parallel_enabled=False)
        # force on
        r = dispatch_parallel(reg, intents, parallel=True, max_workers=4)
        self.assertTrue(all(x.ok for x in r))
        # force off while global on
        configure_concurrency(parallel_enabled=True)
        r2 = dispatch_parallel(reg, intents, parallel=False)
        self.assertTrue(all(x.ok for x in r2))

    def test_async_opt_out(self):
        reg = _reg()

        @reg.action("ping")
        async def ping(ctx, n: int = 0):
            await asyncio.sleep(0)
            return Result.success(n=n)

        intents = [
            Intent(action="ping", args={"n": i}, request_id=f"a{i}") for i in range(12)
        ]
        configure_concurrency(parallel_enabled=False)

        async def run():
            return await dispatch_parallel_async(reg, intents)

        results = asyncio.run(run())
        self.assertEqual([r.meta.get("n") for r in results], list(range(12)))

    def test_env_opt_out(self):
        os.environ["UX_CHANNEL_PARALLEL"] = "false"
        try:
            s = reset_concurrency_settings()
            self.assertFalse(s.parallel_enabled)
            self.assertFalse(should_parallelize(10))
        finally:
            os.environ.pop("UX_CHANNEL_PARALLEL", None)
            reset_concurrency_settings()

    def test_channel_facade_parallel_kw(self):
        from ux_channel import Channel

        reg = _reg()

        @reg.action("z")
        def z(ctx, n: int = 0):
            return Result.success(n=n)

        ch = Channel.from_registry(reg)
        intents = [
            Intent(action="z", args={"n": i}, request_id=f"z{i}") for i in range(8)
        ]
        configure_concurrency(parallel_enabled=True)
        self.assertTrue(all(r.ok for r in ch.dispatch_parallel(intents, parallel=False)))
        self.assertTrue(all(r.ok for r in ch.map_dispatch("z", [{"n": 1}], parallel=False)))


class TestBatchParallelOptIn(unittest.TestCase):
    def tearDown(self):
        reset_concurrency_settings()

    def test_batch_default_sequential(self):
        reg = _reg()
        order: list[int] = []

        @reg.action("seq")
        def seq(ctx, n: int = 0):
            order.append(n)
            return Result.success(n=n)

        items = [{"action": "seq", "args": {"n": i}, "request_id": f"b{i}"} for i in range(8)]
        configure_concurrency(batch_parallel=False)
        env = dispatch_batch(reg, items)
        self.assertTrue(env["ok"])
        self.assertEqual(order, list(range(8)))  # sequential order

    def test_batch_parallel_opt_in_same_results(self):
        reg = _reg()

        @reg.action("echo")
        def echo(ctx, n: int = 0):
            return Result.success(n=n)

        items = [{"action": "echo", "args": {"n": i}, "request_id": f"p{i}"} for i in range(16)]
        env_seq = dispatch_batch(reg, items, parallel=False)
        env_par = dispatch_batch(reg, items, parallel=True, parallel_limit=4)
        self.assertTrue(env_seq["ok"] and env_par["ok"])
        seq_ns = [b["meta"].get("n") for b in env_seq["batch"]]
        par_ns = [b["meta"].get("n") for b in env_par["batch"]]
        self.assertEqual(sorted(seq_ns), sorted(par_ns))
        self.assertEqual(seq_ns, list(range(16)))  # envelope order preserved

    def test_batch_parallel_disabled_when_stop_on_error(self):
        reg = _reg()

        @reg.action("maybe")
        def maybe(ctx, n: int = 0):
            if n == 2:
                return Result.failure("bad_request", "nope")
            return Result.success(n=n)

        items = [{"action": "maybe", "args": {"n": i}, "request_id": f"s{i}"} for i in range(6)]
        env = dispatch_batch(reg, items, stop_on_error=True, parallel=True)
        # stop_on_error forces sequential path; may short-circuit
        self.assertGreaterEqual(len(env["batch"]), 3)

    def test_batch_async_parallel_opt_in(self):
        reg = _reg()

        @reg.action("ping")
        async def ping(ctx, n: int = 0):
            await asyncio.sleep(0)
            return Result.success(n=n)

        items = [{"action": "ping", "args": {"n": i}, "request_id": f"ap{i}"} for i in range(10)]

        async def run():
            return await dispatch_batch_async(reg, items, parallel=True, parallel_limit=4)

        env = asyncio.run(run())
        self.assertTrue(env["ok"])
        self.assertEqual(len(env["batch"]), 10)


if __name__ == "__main__":
    unittest.main()
