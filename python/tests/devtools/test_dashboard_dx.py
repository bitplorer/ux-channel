"""Dashboard smoke — render + CLI suite."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from ux_channel.devtools.cli import main
from ux_channel.devtools.dashboard import (
    build_dashboard_model,
    render_dashboard_html,
    run_dashboard_suite,
)


class TestDashboardDx(unittest.TestCase):
    def test_render_status_and_brand(self):
        model = build_dashboard_model(
            doctor={"ok": True, "hints": ["all good"], "diagnose": {"actions": 3}},
            latencies=[
                {"name": "a", "p50_ms": 1.0, "p95_ms": 2.0, "p99_ms": 3.0, "mean_ms": 1.2},
                {"name": "b", "p50_ms": 0.5, "p95_ms": 0.8, "p99_ms": 1.0, "mean_ms": 0.6},
            ],
        )
        html = render_dashboard_html(model)
        self.assertIn("<svg", html)
        self.assertIn("ux-channel", html)
        self.assertIn("Status", html)
        self.assertIn("p95", html)
        self.assertNotIn("chart.js", html.lower())
        self.assertNotIn("cdn.", html.lower())

    def test_suite_and_cli(self):
        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / "dx"
            model = run_dashboard_suite(
                out_dir=out,
                include_profile=True,
                rounds=4,
                warmup=1,
                profile_rounds=2,
                doctor={"ok": True, "diagnose": {"environment": "test"}, "hints": []},
            )
            self.assertTrue((out / "dashboard.html").is_file())
            self.assertIn("sections", model)
            code = main(["dashboard", "--out", str(out), "--rounds", "4", "--warmup", "1",
                         "--profile-rounds", "2", "--no-profile"])
            self.assertEqual(code, 0)


if __name__ == "__main__":
    unittest.main()
