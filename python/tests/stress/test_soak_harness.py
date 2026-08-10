"""Smoke: soak harness passes inline (SLO gate)."""
from __future__ import annotations

import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


class TestSoakHarness(unittest.TestCase):
    def test_inline_pass(self):
        r = subprocess.run(
            [
                sys.executable,
                str(ROOT / "scripts/soak/harness.py"),
                "--mode",
                "inline",
                "--pairs",
                "5",
                "--actions",
                "20",
                "--peers-ws",
                "1",
                "--report",
                str(ROOT / "soak-report.json"),
            ],
            cwd=str(ROOT),
            env={**dict(**__import__("os").environ), "PYTHONPATH": f"src:."},
            capture_output=True,
            text=True,
            timeout=120,
        )
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("PASS", r.stdout)


if __name__ == "__main__":
    unittest.main()
