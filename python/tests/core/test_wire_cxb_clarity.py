"""
CXB clarity suite — executable mental model.

If these read cleanly and pass, the format is understandable:
  1. One format name: cxb
  2. One media type
  3. Intent / Result / ops round-trip
  4. Frame starts with CXB1 or CXBZ, ends with integrity when uncompressed
  5. Corrupt → clear error, never silent garbage
  6. Same dict API as JSON (isomorphic surface)
"""

from __future__ import annotations

import unittest

from ux_channel.wire import MEDIA_TYPES, decode, encode, reset_wire
from ux_channel.wire.cxb import (
    FORMAT_NAME,
    MAGIC,
    MAGIC_Z,
    MEDIA_TYPE,
    decode_cxb,
    encode_cxb,
    is_cxb,
)


class TestCxbNamingClarity(unittest.TestCase):
    def test_single_public_format_name(self):
        self.assertEqual(FORMAT_NAME, "cxb")
        self.assertEqual(MEDIA_TYPES["cxb"], MEDIA_TYPE)
        self.assertEqual(MEDIA_TYPE, "application/ux-channel+cxb")

    def test_wire_api_uses_format_cxb_only(self):
        reset_wire()
        doc = {"v": "1", "ok": True, "ops": []}
        blob = encode(doc, format="cxb")
        self.assertEqual(blob.format, "cxb")
        self.assertEqual(blob.media_type, MEDIA_TYPE)
        self.assertEqual(decode(blob.data, format="cxb"), decode_cxb(blob.data))


class TestCxbFrameClarity(unittest.TestCase):
    def test_magic_is_readable(self):
        self.assertEqual(MAGIC, b"CXB1")
        self.assertEqual(MAGIC_Z, b"CXBZ")

    def test_small_frame_is_cxb1_with_crc_footer(self):
        raw = encode_cxb({"v": "1", "ok": True, "ops": [{"op": "toast", "message": "x", "level": "info"}]})
        self.assertTrue(is_cxb(raw))
        if raw[:4] == MAGIC:
            self.assertEqual(raw[-8:-4], b"~CRC", "uncompressed frames end with ~CRC+u32")
        else:
            self.assertEqual(raw[:4], MAGIC_Z)

    def test_kind_byte_intent_vs_result(self):
        intent = encode_cxb({"v": "1", "action": "A.b", "args": {}})
        result = encode_cxb({"v": "1", "ok": True, "ops": []})
        # unwrap crc for kind peek
        def kind(raw: bytes) -> int:
            if raw[:4] == MAGIC_Z:
                import zlib

                raw = zlib.decompress(raw[4:])
            if raw[-8:-4] == b"~CRC":
                raw = raw[:-8]
            return raw[4]

        self.assertEqual(kind(intent), 1)  # Intent
        self.assertEqual(kind(result), 2)  # Result


class TestCxbBehaviourClarity(unittest.TestCase):
    def tearDown(self):
        reset_wire()

    def test_same_dict_as_json_surface(self):
        doc = {
            "v": "1",
            "ok": True,
            "ops": [
                {"op": "toast", "message": "hi", "level": "info"},
                {
                    "op": "morph",
                    "target": '[data-channel-id="x"]',
                    "html": "<i>1</i>",
                    "morph": "idiomorph",
                },
            ],
            "meta": {"action": "Demo.run"},
        }
        j = decode(encode(doc, format="json").data, format="json")
        c = decode(encode(doc, format="cxb").data, format="cxb")
        self.assertEqual(j["ok"], c["ok"])
        self.assertEqual(len(j["ops"]), len(c["ops"]))
        self.assertEqual(j["ops"][0]["op"], c["ops"][0]["op"])
        self.assertEqual(j["meta"]["action"], c["meta"]["action"])

    def test_corrupt_error_message_is_clear(self):
        raw = encode_cxb({"v": "1", "ok": True, "ops": []})
        if raw[:4] != MAGIC:
            self.skipTest("compressed")
        bad = raw[:-1] + bytes([raw[-1] ^ 0xFF])
        with self.assertRaises(ValueError) as cm:
            decode_cxb(bad)
        msg = str(cm.exception).lower()
        self.assertTrue("crc" in msg or "corrupt" in msg, msg)

    def test_no_format_aliases(self):
        """Sandbox 0.1: only format name is cxb — no channelbin/channel aliases."""
        from ux_channel.wire import configure_wire, get_policy
        # soft configure unknown alias → stays/falls to safe floor, not a secret cxb alias
        configure_wire(format="json")
        configure_wire(format="channelbin")  # soft → json floor (not cxb)
        self.assertNotEqual(get_policy().format, "channelbin")
        with self.assertRaises(Exception):
            configure_wire(format="channel", strict=True)


class TestCxbReadmeSnippet(unittest.TestCase):
    """The three lines a developer should remember."""

    def test_three_liner(self):
        from ux_channel.wire import encode, decode

        result = {"v": "1", "ok": True, "ops": [{"op": "toast", "message": "ok", "level": "info"}]}
        blob = encode(result, format="cxb")
        back = decode(blob.data)  # sniff / complete works
        self.assertTrue(back["ok"])
        self.assertEqual(blob.media_type, "application/ux-channel+cxb")


if __name__ == "__main__":
    unittest.main()
