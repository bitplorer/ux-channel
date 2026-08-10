"""Internal wire plugins — app API stays encode/decode only."""

from __future__ import annotations

import unittest

from ux_channel.wire import (
    MEDIA_TYPES,
    Codec,
    available_formats,
    clear_codec_cache,
    configure_wire,
    decode,
    encode,
    reset_wire,
)
from ux_channel.wire.cxb import make_cxb_codec
from ux_channel.wire.plugins import (
    list_wire_plugins,
    register_wire_format,
    unregister_wire_format,
)


class TestBuiltinPlugins(unittest.TestCase):
    def tearDown(self):
        try:
            register_wire_format(
                "cxb",
                media_type="application/ux-channel+cxb",
                factory=make_cxb_codec,
                sniff=lambda b: isinstance(b, (bytes, bytearray))
                and bytes(b[:4]) in (b"CXB1", b"CXBZ"),
                media_aliases=("application/cxb",),
                replace=True,
            )
        except Exception:
            pass
        reset_wire()
        clear_codec_cache()

    def test_cxb_is_registered_plugin(self):
        self.assertIn("cxb", list_wire_plugins())
        self.assertIn("cxb", available_formats())
        self.assertEqual(MEDIA_TYPES["cxb"], "application/ux-channel+cxb")

    def test_encode_cxb_via_public_api_only(self):
        blob = encode({"v": "1", "ok": True, "ops": []}, format="cxb")
        self.assertEqual(blob.format, "cxb")
        self.assertTrue(decode(blob.data, format="cxb")["ok"])

    def test_replace_cxb_plugin_internal(self):
        calls = {"n": 0}

        def factory() -> Codec:
            def dumps(obj, *, pretty=False, default=None):
                calls["n"] += 1
                return b"FAKE" + str(obj.get("v", "")).encode()

            def loads(data):
                return {"v": "1", "ok": True, "ops": [], "fake": True}

            return Codec(
                format="cxb",
                engine="fake",
                media_type="application/ux-channel+cxb",
                produces_bytes=True,
                _dumps=dumps,
                _loads=loads,
            )

        register_wire_format(
            "cxb",
            media_type="application/ux-channel+cxb",
            factory=factory,
            sniff=lambda b: bytes(b[:4]) == b"FAKE",
            replace=True,
        )
        clear_codec_cache()
        configure_wire(format="cxb")
        blob = encode({"v": "9", "ok": True, "ops": []}, format="cxb")
        self.assertTrue(blob.data.startswith(b"FAKE"))
        self.assertGreaterEqual(calls["n"], 1)
        self.assertTrue(decode(blob.data, format="cxb")["fake"])

        register_wire_format(
            "cxb",
            media_type="application/ux-channel+cxb",
            factory=make_cxb_codec,
            sniff=lambda b: bytes(b[:4]) in (b"CXB1", b"CXBZ"),
            replace=True,
        )
        clear_codec_cache()
        blob = encode({"v": "1", "ok": True, "ops": []}, format="cxb")
        self.assertIn(blob.data[:4], (b"CXB1", b"CXBZ"))

    def test_register_custom_format_internal(self):
        def factory() -> Codec:
            import json

            def dumps(obj, *, pretty=False, default=None):
                return b"X" + json.dumps(obj).encode()

            def loads(data):
                return json.loads(bytes(data)[1:])

            return Codec(
                format="xjson",
                engine="xjson",
                media_type="application/x-test+json",
                produces_bytes=True,
                _dumps=dumps,
                _loads=loads,
            )

        register_wire_format(
            "xjson",
            media_type="application/x-test+json",
            factory=factory,
            sniff=lambda b: bytes(b[:1]) == b"X",
            replace=True,
        )
        self.assertIn("xjson", available_formats())
        blob = encode({"a": 1}, format="xjson")
        self.assertEqual(decode(blob.data, format="xjson"), {"a": 1})
        unregister_wire_format("xjson")
        self.assertNotIn("xjson", list_wire_plugins())

    def test_cannot_unregister_json(self):
        with self.assertRaises(ValueError):
            unregister_wire_format("json")

    def test_public_wire_hides_plugin_api(self):
        import ux_channel.wire as w

        self.assertFalse(hasattr(w, "register_wire_format"))
        self.assertFalse(hasattr(w, "unregister_wire_format"))
        self.assertFalse(hasattr(w, "list_wire_plugins"))


if __name__ == "__main__":
    unittest.main()
