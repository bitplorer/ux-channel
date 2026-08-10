
"""CXB string interning — no performance/size side effects on uncharted shapes."""

from __future__ import annotations

import threading
import time
import unittest
import zlib

from ux_channel.wire.cxb import (
    INTERN_MIN_FREQ,
    MAGIC_Z,
    MAX_INTERN_ENTRIES,
    decode_cxb,
    encode_cxb,
)


def _table(doc) -> list[str]:
    raw = encode_cxb(doc)
    plain = zlib.decompress(raw[4:]) if raw[:4] == MAGIC_Z else raw
    if plain[-8:-4] == b"~CRC":
        plain = plain[:-8]
    i = 5

    def varint(i):
        shift = 0
        n = 0
        while True:
            b = plain[i]
            i += 1
            n |= (b & 0x7F) << shift
            if not (b & 0x80):
                return n, i
            shift += 7

    n, i = varint(i)
    out = []
    for _ in range(n):
        ln, i = varint(i)
        out.append(plain[i : i + ln].decode("utf-8"))
        i += ln
    return out


class TestInternSafety(unittest.TestCase):
    def test_repeated_tokens_interned(self):
        doc = {
            "v": "1",
            "ok": True,
            "ops": [{"op": "toast", "message": "Saved", "level": "success"}] * 15,
        }
        table = _table(doc)
        self.assertIn("toast", table)
        self.assertIn("Saved", table)
        self.assertEqual(decode_cxb(encode_cxb(doc))["ops"][0]["message"], "Saved")

    def test_unique_messages_not_in_table(self):
        doc = {
            "v": "1",
            "ok": True,
            "ops": [
                {"op": "toast", "message": f"unique-{i}", "level": "info"}
                for i in range(40)
            ],
        }
        table = _table(doc)
        self.assertIn("toast", table)
        self.assertIn("info", table)
        for i in range(40):
            self.assertNotIn(f"unique-{i}", table)
        out = decode_cxb(encode_cxb(doc))
        self.assertEqual(out["ops"][17]["message"], "unique-17")

    def test_single_occurrence_not_interned(self):
        doc = {
            "v": "1",
            "ok": True,
            "ops": [{"op": "toast", "message": "only-once", "level": "info"}],
        }
        table = _table(doc)
        self.assertNotIn("only-once", table)
        self.assertEqual(INTERN_MIN_FREQ, 2)

    def test_html_never_interned(self):
        html = "<div>" + ("cell " * 50) + "</div>"
        doc = {
            "v": "1",
            "ok": True,
            "ops": [
                {
                    "op": "morph",
                    "target": "#a",
                    "html": html,
                    "morph": "idiomorph",
                }
            ]
            * 3,
        }
        table = _table(doc)
        self.assertNotIn(html, table)
        self.assertIn("morph", table)
        self.assertEqual(decode_cxb(encode_cxb(doc))["ops"][0]["html"], html)

    def test_table_bounded(self):
        ops = []
        for i in range(MAX_INTERN_ENTRIES + 100):
            token = f"t{i % 20}"
            ops.append({"op": "toast", "message": token, "level": "info"})
        table = _table({"v": "1", "ok": True, "ops": ops})
        self.assertLessEqual(len(table), MAX_INTERN_ENTRIES)

    def test_encode_latency_scales_near_linear(self):
        def build(n):
            return {
                "v": "1",
                "ok": True,
                "ops": [
                    {"op": "toast", "message": f"m{i}", "level": "info"}
                    for i in range(n)
                ],
            }

        def timed(n, reps=30):
            doc = build(n)
            for _ in range(5):
                encode_cxb(doc)
            t0 = time.perf_counter()
            for _ in range(reps):
                encode_cxb(doc)
            return (time.perf_counter() - t0) / reps

        t50 = timed(50)
        t200 = timed(200)
        self.assertLess(t200 / max(t50, 1e-9), 8.0)

    def test_no_cross_call_table_leak(self):
        a = encode_cxb(
            {
                "v": "1",
                "ok": True,
                "ops": [{"op": "toast", "message": "A", "level": "info"}] * 5,
            }
        )
        b = encode_cxb(
            {
                "v": "1",
                "ok": True,
                "ops": [{"op": "toast", "message": "B", "level": "info"}] * 5,
            }
        )
        self.assertEqual(decode_cxb(a)["ops"][0]["message"], "A")
        self.assertEqual(decode_cxb(b)["ops"][0]["message"], "B")

    def test_parallel_encode_stable(self):
        doc = {
            "v": "1",
            "ok": True,
            "ops": [{"op": "toast", "message": "P", "level": "info"}] * 25,
        }
        err = []

        def worker():
            try:
                for _ in range(40):
                    out = decode_cxb(encode_cxb(doc))
                    assert out["ops"][0]["message"] == "P"
            except Exception as e:
                err.append(repr(e))

        threads = [threading.Thread(target=worker) for _ in range(8)]
        for th in threads:
            th.start()
        for th in threads:
            th.join()
        self.assertEqual(err, [])


if __name__ == "__main__":
    unittest.main()
