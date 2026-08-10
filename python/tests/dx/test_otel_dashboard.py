"""OpenTelemetry + dashboard observability section."""

from __future__ import annotations

import unittest

from ux_channel.ops_dx.dx_dashboard import (
    USE_CASES,
    build_dashboard_model,
    clear_plugins,
    reset_dashboard_settings,
)
from ux_channel.ops_dx.otel import (
    attach_otel,
    dashboard_snapshot,
    detach_otel,
    otel_available,
    status,
)
from ux_channel.ops_dx.trace import FrameKind, TraceConfig, get_tracer


class TestOtelDashboard(unittest.TestCase):
    def setUp(self):
        detach_otel()
        clear_plugins(keep_builtins=True)
        reset_dashboard_settings()
        get_tracer().configure(TraceConfig(enabled=True, retain=100, capture_payloads=False))
        get_tracer().clear()

    def tearDown(self):
        detach_otel()
        get_tracer().configure(TraceConfig(enabled=False))

    def test_use_case_includes_observability(self):
        ids = [u["id"] for u in USE_CASES]
        self.assertIn("observability", ids)
        self.assertLess(ids.index("policy"), ids.index("observability"))
        self.assertLess(ids.index("observability"), ids.index("subsystems"))

    def test_dashboard_snapshot_no_payloads(self):
        tr = get_tracer()
        tr.emit(
            FrameKind.INTENT_IN,
            "in",
            request_id="r1",
            action="echo",
            detail={"password": "x", "n": 1},
        )
        tr.emit(
            FrameKind.RESULT_OUT,
            "out",
            request_id="r1",
            action="echo",
            ok=True,
            duration_ms=1.2,
        )
        snap = dashboard_snapshot()
        self.assertIn("otel", snap)
        self.assertIn("channel_tracer", snap)
        recent = snap["channel_tracer"]["recent"]
        self.assertTrue(recent)
        blob = str(recent)
        self.assertNotIn("password", blob)
        self.assertNotIn('"n": 1', blob)  # detail not included

    def test_model_observability_section(self):
        model = build_dashboard_model(
            doctor={
                "ok": True,
                "environment": "development",
                "observe": "otel",
                "diagnose": {"observe": "otel", "actions": 1},
            },
            latencies=[],
        )
        obs = model["sections"]["observability"]
        self.assertIn("otel", obs)
        self.assertEqual(obs.get("observe_mode"), "otel")
        ids = [p["id"] for p in model["panels"]]
        self.assertIn("core.observability", ids)

    def test_attach_idempotent(self):
        a = attach_otel()
        b = attach_otel()
        st = status()
        self.assertEqual(st["attached"], bool(a))
        # second call still attached if first succeeded
        if otel_available():
            self.assertTrue(a and b and st["attached"])
        detach_otel()
        self.assertFalse(status()["attached"])

    def test_request_scoped_spans_when_sdk_present(self):
        if not otel_available():
            self.skipTest("opentelemetry not installed")
        from opentelemetry import trace as otel_trace
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export.in_memory_span_exporter import (
            InMemorySpanExporter,
        )
        from opentelemetry.sdk.trace.export import SimpleSpanProcessor

        exporter = InMemorySpanExporter()
        provider = TracerProvider()
        provider.add_span_processor(SimpleSpanProcessor(exporter))
        otel_trace.set_tracer_provider(provider)

        detach_otel()
        self.assertTrue(attach_otel())
        tr = get_tracer()
        tr.emit(FrameKind.INTENT_IN, "in", request_id="req-9", action="echo")
        tr.emit(
            FrameKind.HANDLER_END,
            "done",
            request_id="req-9",
            action="echo",
            ok=True,
            duration_ms=0.5,
        )
        tr.emit(
            FrameKind.RESULT_OUT,
            "out",
            request_id="req-9",
            action="echo",
            ok=True,
            duration_ms=0.6,
        )
        spans = exporter.get_finished_spans()
        names = [s.name for s in spans]
        self.assertTrue(any(n.startswith("ux.channel.") for n in names))
        # root should exist
        self.assertIn("ux.channel.request", names)
        detach_otel()


if __name__ == "__main__":
    unittest.main()
