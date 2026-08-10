"""Error handling examples — patterns stay correct and mapped."""

from __future__ import annotations

import unittest

from ux_channel.protocol.error_map import ensure_error_meta, http_status_for
from ux_channel.protocol.errors import ActionError
from ux_channel.host.registry import ActionRegistry
from ux_channel.protocol.types import Intent, Result

# Import examples package via path
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "examples" / "error_handling"))

from patterns import (  # noqa: E402
    pattern_ch_fail_auth,
    pattern_ch_fail_code,
    pattern_ch_fail_forbidden,
    pattern_ch_fail_rate,
    pattern_ch_fail_valid,
    pattern_dx_usage,
    pattern_handler_with_fail,
    pattern_map_status,
    pattern_raise_action_error,
    pattern_result_failure,
    pattern_retryable_rate,
    run_all,
    _boot_channel,
)


class TestErrorHandlingExamples(unittest.TestCase):
    def test_result_failure_validation(self):
        r = pattern_result_failure()
        self.assertFalse(r.ok)
        self.assertEqual(r.error.code, "validation")
        self.assertIn("email", r.error.fields or {})
        self.assertGreaterEqual(len(r.ops), 1)
        ensure_error_meta(r)
        self.assertEqual(http_status_for(r), 422)

    def test_rate_retryable(self):
        r = pattern_retryable_rate()
        self.assertEqual(r.error.code, "rate_limited")
        self.assertTrue(r.error.retryable)
        self.assertEqual(r.meta.get("retry_after"), 30)
        ensure_error_meta(r)
        self.assertEqual(http_status_for(r), 429)

    def test_action_error_via_registry(self):
        reg = ActionRegistry(
            secret="error-examples-secret-key-32chars!!!",
            require_cap=False,
        )
        r = pattern_raise_action_error(reg)
        self.assertFalse(r.ok)
        self.assertEqual(r.error.code, "validation")

    def test_ch_fail_plane(self):
        ch = _boot_channel()
        cases = [
            (pattern_ch_fail_valid, "validation", 422),
            (pattern_ch_fail_auth, "unauthorized", 401),
            (pattern_ch_fail_forbidden, "forbidden", 403),
            (pattern_ch_fail_rate, "rate_limited", 429),
            (pattern_ch_fail_code, "conflict", 409),
        ]
        for fn, code, status in cases:
            r = fn(ch)
            m = pattern_map_status(r)
            self.assertEqual(m["code"], code, fn.__name__)
            self.assertEqual(m["http_status"], status, fn.__name__)
            self.assertFalse(m["ok"])

    def test_handler_insufficient_funds(self):
        ch = _boot_channel()
        r = pattern_handler_with_fail(ch)
        self.assertFalse(r.ok)
        self.assertEqual(r.error.code, "forbidden")

    def test_dx_usage(self):
        d = pattern_dx_usage()
        self.assertEqual(d["code"], "dx.usage")
        self.assertEqual(d["exit_code"], 2)
        self.assertTrue(d["hint"])

    def test_run_all(self):
        rows = run_all()
        names = {r["name"] for r in rows}
        self.assertIn("result_failure", names)
        self.assertIn("ch_fail_valid", names)
        self.assertIn("handler_with_fail", names)
        self.assertIn("dx_usage", names)
        self.assertGreaterEqual(len(rows), 8)


if __name__ == "__main__":
    unittest.main()
