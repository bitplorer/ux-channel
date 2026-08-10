"""Production maturity — policy atomicity, concurrent encode (public API)."""

from __future__ import annotations

import threading
import unittest

from ux_channel.wire import (
    available_formats,
    clear_codec_cache,
    configure_wire,
    decode,
    encode,
    get_policy,
    reset_wire,
)
from ux_channel.wire.cxb import make_cxb_codec
from ux_channel.wire.plugins import register_wire_format


class TestMaturity(unittest.TestCase):
    def tearDown(self):
        register_wire_format(
            "cxb",
            media_type="application/ux-channel+cxb",
            factory=make_cxb_codec,
            sniff=lambda b: isinstance(b, (bytes, bytearray))
            and bytes(b[:4]) in (b"CXB1", b"CXBZ"),
            media_aliases=("application/cxb",),
            replace=True,
        )
        reset_wire()
        clear_codec_cache()

    def test_soft_configure_never_bricks(self):
        configure_wire(format="json")
        configure_wire(format="not-a-real-format")
        self.assertEqual(get_policy().format, "json")
        self.assertTrue(encode({"a": 1}).data)

    def test_strict_configure_raises(self):
        with self.assertRaises(ValueError):
            configure_wire(format="nope", strict=True)

    def test_json_always_available(self):
        self.assertIn("json", available_formats())
        blob = encode({"ok": True}, format="json")
        self.assertEqual(decode(blob.data, format="json")["ok"], True)

    def test_cxb_works_without_plugin_knowledge(self):
        self.assertIn("cxb", available_formats())
        blob = encode({"v": "1", "ok": True, "ops": []}, format="cxb")
        self.assertEqual(blob.format, "cxb")
        self.assertTrue(decode(blob.data, format="cxb")["ok"])

    def test_concurrent_configure_and_encode(self):
        errors: list[str] = []

        def cfg():
            try:
                for _ in range(50):
                    configure_wire(format="json")
                    configure_wire(format="cxb")
            except Exception as e:
                errors.append(repr(e))

        def enc():
            try:
                for _ in range(80):
                    doc = {
                        "v": "1",
                        "ok": True,
                        "ops": [{"op": "toast", "message": "x", "level": "info"}],
                    }
                    b = encode(doc, format="cxb")
                    decode(b.data, format="cxb")
                    encode(doc, format="json")
            except Exception as e:
                errors.append(repr(e))

        threads = [threading.Thread(target=cfg)] + [
            threading.Thread(target=enc) for _ in range(4)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        self.assertEqual(errors, [])
        self.assertTrue(encode({"a": 1}, format="json").data)


if __name__ == "__main__":
    unittest.main()
