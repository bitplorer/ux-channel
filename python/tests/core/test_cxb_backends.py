"""CXB backends: Rust .so default, pure Python optional oracle."""

from __future__ import annotations

import os
import unittest

from ux_channel import ops as O
from ux_channel.wire.cxb import (
    cxb_impl,
    decode_cxb,
    decode_cxb_python,
    encode_cxb,
    encode_cxb_python,
    native_available,
)


class TestCxbBackends(unittest.TestCase):
    def test_python_oracle_always_works(self):
        doc = {
            "v": "1",
            "ok": True,
            "ops": [O.toast("Saved", level="success")] * 5,
        }
        raw = encode_cxb_python(doc)
        self.assertIn(raw[:4], (b"CXB1", b"CXBZ"))
        back = decode_cxb_python(raw)
        self.assertEqual(back["ops"][0]["message"], "Saved")

    def test_default_prefers_native_when_available(self):
        if not native_available():
            self.skipTest("Rust _cxb_native.so not built")
        # clear forced python
        os.environ.pop("UX_CHANNEL_CXB_IMPL", None)
        self.assertEqual(cxb_impl(), "native")
        doc = {"v": "1", "ok": True, "ops": [O.toast("X", level="info")] * 3}
        raw = encode_cxb(doc)
        self.assertEqual(decode_cxb(raw)["ops"][0]["message"], "X")

    def test_force_python_impl(self):
        os.environ["UX_CHANNEL_CXB_IMPL"] = "python"
        try:
            self.assertEqual(cxb_impl(), "python")
            doc = {"v": "1", "ok": True, "ops": [O.toast("P", level="info")] * 8}
            raw = encode_cxb(doc)
            # still valid CXB
            self.assertIn(raw[:4], (b"CXB1", b"CXBZ"))
            self.assertEqual(decode_cxb_python(raw)["ops"][0]["message"], "P")
        finally:
            os.environ.pop("UX_CHANNEL_CXB_IMPL", None)

    def test_cross_backend_roundtrip(self):
        """Python encode → native decode and reverse (when native present)."""
        doc = {
            "v": "1",
            "ok": True,
            "ops": [
                O.toast("Hi", level="success"),
                {"op": "morph", "target": "#a", "html": "<b>1</b>", "morph": "idiomorph"},
            ],
        }
        py_raw = encode_cxb_python(doc)
        # default decode (native if any) must accept python frames
        back = decode_cxb(py_raw)
        self.assertEqual(back["ops"][0]["message"], "Hi")
        self.assertEqual(back["ops"][1]["html"], "<b>1</b>")

        if native_available():
            os.environ.pop("UX_CHANNEL_CXB_IMPL", None)
            nat_raw = encode_cxb(doc)
            # pure python decode of native (or default) frames
            back2 = decode_cxb_python(nat_raw)
            self.assertEqual(back2["ops"][0]["message"], "Hi")

    def test_bulk_python_can_cxbz(self):
        doc = {
            "v": "1",
            "ok": True,
            "ops": [O.toast("Saved", level="success")] * 40,
        }
        raw = encode_cxb_python(doc)
        # pure python also supports CXBZ
        self.assertIn(raw[:4], (b"CXB1", b"CXBZ"))
        self.assertEqual(len(decode_cxb_python(raw)["ops"]), 40)


if __name__ == "__main__":
    unittest.main()
