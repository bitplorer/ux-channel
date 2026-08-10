"""Systematic p95 + flamegraph artifacts for ux-channel (maintainer-facing)."""

from __future__ import annotations

import json
import unittest
from pathlib import Path

from ux_channel.transport.concurrency import dispatch_parallel
from ux_channel.ops_dx.profiling import measure_latency, run_suite
from ux_channel.host.registry import ActionRegistry
from ux_channel.protocol.types import Intent, Result

REPORTS = Path(__file__).resolve().parents[2] / "reports" / "p95_test"


class TestP95Profiling(unittest.TestCase):
    def test_suite_writes_flamegraph_artifacts(self):
        reg = ActionRegistry(
            secret="test-secret-key-32chars-minimum!!!!", require_cap=False
        )

        @reg.action("echo")
        def echo(ctx, n: int = 0):
            return Result.success(n=n)

        intents = [
            Intent(action="echo", args={"n": i}, request_id=f"r{i}") for i in range(20)
        ]

        def one():
            reg.dispatch(Intent(action="echo", args={"n": 0}, request_id="x"))

        def many():
            dispatch_parallel(reg, intents)

        report = run_suite(
            [("dispatch_one", one), ("dispatch_parallel_20", many)],
            out_dir=REPORTS,
            title="ux-channel p95 test",
            rounds=30,
            warmup=3,
            profile_rounds=12,
        )
        self.assertTrue((REPORTS / "latency.json").is_file())
        self.assertTrue((REPORTS / "profile.speedscope.json").is_file())
        self.assertTrue((REPORTS / "report.html").is_file())
        ss = json.loads((REPORTS / "profile.speedscope.json").read_text())
        self.assertIn("profiles", ss)
        for lat in report["latencies"]:
            self.assertLess(lat["p95_ms"], 100.0, msg=lat)

    def test_day1_dispatch_no_concurrency_api(self):
        reg = ActionRegistry(
            secret="test-secret-key-32chars-minimum!!!!", require_cap=False
        )

        @reg.action("ok")
        def ok(ctx):
            return Result.success()

        r = reg.dispatch(Intent(action="ok", args={}, request_id="1"))
        self.assertTrue(r.ok)


if __name__ == "__main__":
    unittest.main()
