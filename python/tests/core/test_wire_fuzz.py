# Copyright (c) 2026 UX-CHANNEL
"""CI-budget mutational fuzzer (AFL-style) for wire codecs.

Full long runs: ``PYTHONPATH=src python scripts/fuzz_wire.py --seconds 60``
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

# import harness
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
from fuzz_wire import build_seed_corpus, fuzz_for  # noqa: E402


class TestWireFuzz(unittest.TestCase):
    def test_seed_corpus_nonempty(self):
        seeds = build_seed_corpus()
        self.assertGreater(len(seeds), 10)
        self.assertIn(b"", seeds)

    def test_mutational_fuzz_no_crashes(self):
        stats = fuzz_for(seconds=2.0, seed=42, max_iters=4000)
        self.assertGreater(stats.iterations, 100)
        self.assertEqual(
            stats.crashes,
            0,
            msg=f"unique crashes: {stats.unique_crashes}",
        )
        # progress on all formats
        self.assertTrue(stats.by_format)


if __name__ == "__main__":
    unittest.main()
