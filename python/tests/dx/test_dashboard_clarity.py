"""Clarity: no legacy dashboard surfaces; model matches use-case design."""

from __future__ import annotations

import ast
import inspect
import unittest
from pathlib import Path

import ux_channel.ops_dx.dx_dashboard as dx


class TestDashboardClarity(unittest.TestCase):
    def test_public_api_is_minimal(self):
        allowed = set(dx.__all__)
        # must have integrity core
        for name in (
            "USE_CASES",
            "build_dashboard_model",
            "render_dashboard_html",
            "Widget",
            "Panel",
            "register_plugin",
        ):
            self.assertIn(name, allowed)
        # must not export legacy
        for name in (
            "Asset",
            "Contribution",
            "DashboardPlugin",
            "DashboardContext",
            "emit_slots",
        ):
            self.assertNotIn(name, allowed)
            self.assertFalse(hasattr(dx, name), name)

    def test_source_has_no_legacy_strings(self):
        src = Path(dx.__file__).read_text(encoding="utf-8")
        forbidden = [
            "on_connect",
            "dxConnect",
            "customElements.define",
            "Chart.js",
            "cdn.",
            "emit_slots",
            "class Asset",
            "DashboardPlugin",
        ]
        for token in forbidden:
            self.assertNotIn(token, src, f"stale token in source: {token}")

    def test_configure_signature_no_paths(self):
        sig = inspect.signature(dx.configure_dashboard)
        for bad in ("scripts", "styles", "assets"):
            self.assertNotIn(bad, sig.parameters)

    def test_use_case_order(self):
        ids = [u["id"] for u in dx.USE_CASES]
        self.assertEqual(
            ids,
            [
                "status",
                "guidance",
                "performance",
                "inventory",
                "policy",
                "observability",
                "subsystems",
                "extensions",
            ],
        )

    def test_model_schema_sections(self):
        model = dx.build_dashboard_model(
            doctor={"ok": True, "environment": "development", "hints": ["h"]},
            latencies=[],
        )
        self.assertEqual(model["schema"], dx.DASHBOARD_MODEL_SCHEMA)
        self.assertEqual(dx.DASHBOARD_MODEL_SCHEMA, 1)
        self.assertIn("sections", model)
        self.assertIn("status", model["sections"])
        self.assertIn("integrity", model)
        self.assertFalse(model["sections"]["performance"]["available"])
        # panels tagged with use_case for core
        core = [p for p in model["panels"] if p["id"].startswith("core.")]
        self.assertTrue(core)
        self.assertTrue(all(p.get("use_case") for p in core))

    def test_shell_has_no_ce_bootstrap(self):
        html = dx.render_dashboard_html(
            dx.build_dashboard_model(doctor={"ok": True}, latencies=[])
        )
        self.assertNotIn("dxConnect", html)
        self.assertNotIn("customElements.define", html)
        self.assertIn("Status", html)

    def test_module_parses_clean(self):
        src = Path(dx.__file__).read_text(encoding="utf-8")
        tree = ast.parse(src)
        # no Assign to Panel.json after class (legacy patch style)
        assigns = [
            n
            for n in ast.walk(tree)
            if isinstance(n, ast.Assign)
            and any(
                isinstance(t, ast.Attribute) and t.attr == "json"
                for t in n.targets
                if isinstance(t, ast.Attribute)
            )
        ]
        self.assertEqual(assigns, [], "Panel.json should be a real class method, not patched")


if __name__ == "__main__":
    unittest.main()
