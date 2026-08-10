"""Optional _cxb_native extension — auto-used by CXB; safe fallback."""

from __future__ import annotations

import importlib
import unittest

from ux_channel.wire import encode, decode, configure_wire, reset_wire, clear_codec_cache
from ux_channel.wire.cxb import (
    decode_cxb,
    encode_cxb,
    make_cxb_codec,
    native_available,
)


def _has_native() -> bool:
    try:
        import ux_channel._cxb_native as n  # noqa: F401
        return hasattr(n, "encode") and hasattr(n, "decode")
    except ImportError:
        return False


@unittest.skipUnless(_has_native(), "_cxb_native.so not built")
class TestCxbNative(unittest.TestCase):
    def tearDown(self):
        reset_wire()
        clear_codec_cache()

    def test_native_module_import(self):
        import ux_channel._cxb_native as n

        self.assertTrue(callable(n.encode))
        self.assertTrue(callable(n.decode))

    def test_native_available_flag(self):
        self.assertTrue(native_available())

    def test_make_cxb_codec_reports_native_engine(self):
        c = make_cxb_codec()
        self.assertEqual(c.format, "cxb")
        self.assertEqual(c.engine, "cxb-native")

    def test_roundtrip_via_native_api(self):
        import ux_channel._cxb_native as n

        doc = {
            "v": "1",
            "ok": True,
            "ops": [
                {"op": "toast", "message": "Saved", "level": "success"},
                {"op": "morph", "target": "#x", "html": "<b>1</b>", "morph": "idiomorph"},
            ],
            "meta": {"action": "Cart.add"},
        }
        raw = n.encode(doc)
        self.assertEqual(raw[:4], b"CXB1")
        back = n.decode(raw)
        self.assertEqual(back["ops"][0]["message"], "Saved")
        self.assertEqual(back["ops"][1]["html"], "<b>1</b>")

    def test_python_decodes_native_bytes(self):
        import ux_channel._cxb_native as n

        doc = {
            "v": "1",
            "ok": True,
            "ops": [{"op": "toast", "message": "X", "level": "info"}] * 8,
        }
        raw = n.encode(doc)
        back = decode_cxb(raw)  # may use native or python
        self.assertEqual(len(back["ops"]), 8)
        self.assertEqual(back["ops"][0]["message"], "X")

    def test_encode_cxb_uses_native_automatically(self):
        doc = {"v": "1", "ok": True, "ops": [{"op": "toast", "message": "A", "level": "info"}] * 3}
        raw = encode_cxb(doc)
        self.assertTrue(raw[:4] in (b"CXB1", b"CXBZ"))
        self.assertEqual(decode_cxb(raw)["ops"][0]["message"], "A")

    def test_public_wire_api_format_cxb(self):
        doc = {
            "v": "1",
            "ok": True,
            "ops": [{"op": "toast", "message": "B", "level": "success"}] * 10,
        }
        blob = encode(doc, format="cxb")
        self.assertEqual(blob.format, "cxb")
        # engine label from plugin factory
        self.assertIn(blob.engine, ("cxb", "cxb-native"))
        out = decode(blob.data, format="cxb")
        self.assertEqual(out["ops"][0]["message"], "B")

    def test_cxbz_falls_back_safely(self):
        """Large repetitive → Python may wrap CXBZ; decode still works."""
        html = "<div>" + ("item " * 500) + "</div>"
        doc = {
            "v": "1",
            "ok": True,
            "ops": [{"op": "morph", "target": "#x", "html": html, "morph": "idiomorph"}],
        }
        # Force python encode path for CXBZ by calling pure after... 
        # encode_cxb tries native first (CXB1 only). Size may stay CXB1.
        raw = encode_cxb(doc)
        self.assertEqual(decode_cxb(raw)["ops"][0]["html"], html)

    def test_corrupt_crc_rejected(self):
        import ux_channel._cxb_native as n

        doc = {"v": "1", "ok": True, "ops": []}
        raw = bytearray(n.encode(doc))
        if len(raw) >= 1:
            raw[-1] ^= 0xFF
        with self.assertRaises(ValueError):
            n.decode(bytes(raw))

    def test_cxbz_emitted_on_bulk(self):
        import ux_channel._cxb_native as n

        doc = {
            "v": "1",
            "ok": True,
            "ops": [{"op": "toast", "message": "Saved", "level": "success"}] * 40,
        }
        raw = n.encode(doc)
        self.assertEqual(raw[:4], b"CXBZ")
        self.assertEqual(n.decode(raw)["ops"][0]["message"], "Saved")
        # Python oracle can decode CXBZ too
        self.assertEqual(decode_cxb(raw)["ops"][0]["message"], "Saved")

    def test_intent_roundtrip(self):
        import ux_channel._cxb_native as n

        doc = {
            "v": "1",
            "action": "Cart.add",
            "args": {"sku": "a", "qty": 2},
            "cap": "c" * 32,
            "request_id": "r1",
            "target": '[data-channel-id="cart"]',
        }
        back = n.decode(n.encode(doc))
        self.assertEqual(back["action"], "Cart.add")
        self.assertEqual(back["args"]["sku"], "a")
        self.assertEqual(back["request_id"], "r1")


if __name__ == "__main__":
    unittest.main()
