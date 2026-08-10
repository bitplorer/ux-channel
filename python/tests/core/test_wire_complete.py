"""Completion recovery + CXB integrity under concurrency."""

from __future__ import annotations

import threading
import unittest

from ux_channel.wire import (
    decode,
    encode,
    encode_http_body,
    reset_wire,
)
from ux_channel.wire.cxb import decode_cxb, encode_cxb
from ux_channel.wire.negotiate import response_headers_for


def _doc():
    return {
        "v": "1",
        "ok": True,
        "ops": [
            {"op": "toast", "message": "Saved", "level": "success"},
            {
                "op": "morph",
                "target": '[data-channel-id="c"]',
                "html": "<b>1</b>",
                "morph": "idiomorph",
            },
        ],
        "meta": {"action": "Cart.add"},
    }


class TestCompleteRecovery(unittest.TestCase):
    def tearDown(self):
        reset_wire()

    def test_mislabeled_cxb_still_decodes(self):
        blob = encode(_doc(), format="cxb")
        # Client claims JSON but body is CXB — complete chain sniffs + recovers
        out = decode(blob.data, format="json", complete=True)
        self.assertTrue(out["ok"])
        self.assertEqual(len(out["ops"]), 2)

    def test_strict_no_complete_raises_on_mislabeled(self):
        blob = encode(_doc(), format="cxb")
        with self.assertRaises(Exception):
            decode(blob.data, format="json", complete=False)

    def test_http_encode_fallback_headers(self):
        # Prefer a nonsense format via encode chain: force preferred by policy cxb
        blob = encode_http_body(_doc(), accept="application/ux-channel+cxb")
        self.assertIn(blob.format, ("cxb", "json", "msgpack"))
        h = response_headers_for(blob)
        self.assertEqual(h["X-Channel-Wire"], blob.format)
        if blob.fallback:
            self.assertEqual(h.get("X-Channel-Wire-Fallback"), "1")


class TestCxbIntegrity(unittest.TestCase):
    def test_crc_footer_present_and_verified(self):
        raw = encode_cxb(_doc())
        if raw[:4] == b"CXBZ":
            import zlib

            raw = zlib.decompress(raw[4:])
        self.assertEqual(raw[-8:-4], b"~CRC")
        self.assertEqual(decode_cxb(encode_cxb(_doc()))["ok"], True)

    def test_corrupt_crc_rejected(self):
        raw = encode_cxb(_doc())
        if raw[:4] == b"CXBZ":
            self.skipTest("compressed frame — flip after inflate path covered elsewhere")
        bad = raw[:-1] + bytes([raw[-1] ^ 0xFF])
        with self.assertRaises(ValueError) as cm:
            decode_cxb(bad)
        self.assertIn("CRC", str(cm.exception))

    def test_parallel_encode_decode_no_corruption(self):
        doc = _doc()
        errors: list[str] = []

        def worker(n: int):
            try:
                for i in range(100):
                    d = {
                        "v": "1",
                        "ok": True,
                        "ops": [{"op": "toast", "message": f"{n}-{i}", "level": "info"}] * 5,
                        "meta": {"w": n, "i": i},
                    }
                    raw = encode_cxb(d)
                    out = decode_cxb(raw)
                    assert out["meta"]["w"] == n
                    assert out["ops"][0]["message"] == f"{n}-{i}"
            except Exception as exc:  # noqa: BLE001
                errors.append(repr(exc))

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(12)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        self.assertEqual(errors, [])

    def test_shared_dict_mutation_during_encode(self):
        shared = _doc()
        errors: list[str] = []

        def mutator():
            for i in range(1000):
                shared["ops"][0]["message"] = f"m{i}"
                shared["meta"]["action"] = f"A{i}"

        def encoder():
            try:
                for _ in range(400):
                    blob = encode(shared, format="cxb")
                    out = decode(blob.data, format="cxb")
                    assert out["ok"] is True
                    assert isinstance(out["ops"][0]["message"], str)
            except Exception as exc:  # noqa: BLE001
                errors.append(repr(exc))

        threads = [threading.Thread(target=mutator) for _ in range(2)] + [
            threading.Thread(target=encoder) for _ in range(6)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        self.assertEqual(errors, [])


if __name__ == "__main__":
    unittest.main()
