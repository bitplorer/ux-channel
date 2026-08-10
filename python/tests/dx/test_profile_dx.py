"""First-class DX: uxchannel profile."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from ux_channel.cli import main


class TestProfileDx(unittest.TestCase):
    def test_cli_profile(self):
        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / "p95"
            code = main(
                [
                    "profile",
                    "--out",
                    str(out),
                    "--rounds",
                    "6",
                    "--warmup",
                    "1",
                    "--profile-rounds",
                    "3",
                ]
            )
            self.assertEqual(code, 0)
            self.assertTrue((out / "report.html").is_file())
            self.assertTrue((out / "profile.speedscope.json").is_file())
            self.assertTrue((out / "latency.json").is_file())


if __name__ == "__main__":
    unittest.main()
