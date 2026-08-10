"""Dashboard — use-case sections, integrity, extensions."""

from __future__ import annotations

import inspect
import json
import tempfile
import unittest
from pathlib import Path

from ux_channel.ops_dx.dx_dashboard import (
    Panel,
    Widget,
    build_dashboard_model,
    clear_plugins,
    configure_dashboard,
    list_plugins,
    register_plugin,
    render_dashboard_html,
    reset_dashboard_settings,
    unregister_plugin,
    write_dashboard,
    USE_CASES,
)


class _Extra:
    id = "test.extra"
    order = 50

    def contribute(self, ctx):
        return [
            Panel.as_html("test.extra.main", "Extra", "<p>hello-plugin</p>", order=50),
            Widget("test.extra.w", "W", props={"n": 3}, body="n={n}", order=51),
        ]


class _Boom:
    id = "test.boom"
    order = 1

    def contribute(self, ctx):
        raise RuntimeError("nope")


class DashboardTests(unittest.TestCase):
    def setUp(self):
        clear_plugins(keep_builtins=True)
        reset_dashboard_settings()

    def tearDown(self):
        clear_plugins(keep_builtins=True)
        reset_dashboard_settings()

    def test_use_cases_declared(self):
        self.assertGreaterEqual(len(USE_CASES), 6)
        ids = [u["id"] for u in USE_CASES]
        self.assertEqual(ids[0], "status")
        self.assertIn("performance", ids)

    def test_sections_integrity(self):
        model = build_dashboard_model(
            doctor={
                "ok": True,
                "environment": "development",
                "path": "/ux-channel",
                "regions": 0,
                "hints": ["keep secrets out"],
                "diagnose": {
                    "actions": 3,
                    "require_cap": False,
                    "secret": "SHOULD_NOT_LEAK",
                    "bridge": {"ok": True},
                },
            },
            latencies=[{"name": "a", "p50_ms": 1, "p95_ms": 2, "p99_ms": 3, "mean_ms": 1.2}],
        )
        self.assertEqual(model["schema"], 1)
        sec = model["sections"]
        self.assertTrue(sec["status"]["ok"])
        self.assertTrue(sec["performance"]["available"])
        self.assertEqual(sec["inventory"]["actions"], 3)
        # secret redacted in subsystems/policy path — secret key in diagnose not in inventory
        scrubbed = json.dumps(sec["subsystems"])
        self.assertNotIn("SHOULD_NOT_LEAK", scrubbed)
        ids = [p["id"] for p in model["panels"]]
        self.assertIn("core.status", ids)
        self.assertIn("core.performance.chart", ids)
        self.assertIn("core.inventory", ids)

    def test_performance_missing_is_honest(self):
        model = build_dashboard_model(doctor={"ok": True}, latencies=[])
        self.assertFalse(model["sections"]["performance"]["available"])
        self.assertIn("No samples", model["sections"]["performance"]["note"] or "")

    def test_register_extension(self):
        register_plugin(_Extra())
        model = build_dashboard_model(doctor={}, latencies=[])
        ids = [p["id"] for p in model["panels"]]
        self.assertIn("test.extra.main", ids)
        html = render_dashboard_html(model)
        self.assertIn("hello-plugin", html)
        self.assertIn("n=3", html)

    def test_widget_auto_and_body(self):
        class P:
            id = "p"
            order = 50

            def contribute(self, ctx):
                return [
                    Widget("p.kv", "KV", props={"benches": 2}),
                    Widget("p.b", "B", props={"label": "tracked", "n": 7}, body="{label}: {n}"),
                ]

        register_plugin(P())
        model = build_dashboard_model(doctor={}, latencies=[])
        by_id = {p["id"]: p for p in model["panels"]}
        self.assertIn("ux-dx-props", by_id["p.kv"]["html"])
        html = render_dashboard_html(model)
        self.assertIn("tracked: 7", html)

    def test_disable_builtins(self):
        register_plugin(_Extra())
        configure_dashboard(builtins_enabled=False)
        ids = [p["id"] for p in build_dashboard_model(doctor={}, latencies=[])["panels"]]
        self.assertTrue(all(not i.startswith("core.") and not i.startswith("builtin.") for i in ids))

    def test_disable_one(self):
        register_plugin(_Extra())
        configure_dashboard(disabled_plugins=["test.extra"])
        ids = [p["id"] for p in build_dashboard_model(doctor={}, latencies=[])["panels"]]
        self.assertNotIn("test.extra.main", ids)

    def test_shell_none(self):
        configure_dashboard(shell="none")
        self.assertIn("model-only", render_dashboard_html(build_dashboard_model(doctor={"ok": True})))

    def test_unregister_and_failure(self):
        register_plugin(_Extra())
        self.assertTrue(unregister_plugin("test.extra"))
        register_plugin(_Boom())
        ids = [p["id"] for p in build_dashboard_model(doctor={}, latencies=[])["panels"]]
        self.assertIn("error.test.boom", ids)

    def test_write_no_ce_js(self):
        with tempfile.TemporaryDirectory() as td:
            path = write_dashboard(td, doctor={"ok": True, "hints": ["x"]}, latencies=[])
            data = json.loads((Path(td) / "dashboard.json").read_text())
            self.assertEqual(data["schema"], 1)
            self.assertIn("sections", data)
            html = path.read_text()
            self.assertNotIn("customElements.define", html)
            self.assertNotIn("dxConnect", html)

    def test_configure_no_paths(self):
        sig = inspect.signature(configure_dashboard)
        self.assertNotIn("scripts", sig.parameters)


if __name__ == "__main__":
    unittest.main()
