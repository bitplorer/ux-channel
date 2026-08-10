"""CXB domain binary — denser than generic msgpack on multi-op Results; no codegen."""

from __future__ import annotations

import json
import unittest

from ux_channel.wire import (
    MEDIA_TYPES,
    available_formats,
    configure_wire,
    decode,
    encode,
    reset_wire,
)
from ux_channel.wire.cxb import decode_cxb, encode_cxb, is_cxb


def _result_many():
    return {
        "v": "1",
        "ok": True,
        "ops": (
            [{"op": "toast", "message": "Saved", "level": "success"} for _ in range(12)]
            + [
                {
                    "op": "morph",
                    "target": '[data-channel-id="cart"]',
                    "html": "<b>1</b>",
                    "morph": "idiomorph",
                }
                for _ in range(4)
            ]
        ),
        "meta": {"action": "Cart.add", "request_id": "r1", "runtime": "0.1.0"},
    }


class TestCxbRoundtrip(unittest.TestCase):
    def tearDown(self):
        reset_wire()

    def test_format_registered(self):
        self.assertIn("cxb", available_formats())
        self.assertEqual(MEDIA_TYPES["cxb"], "application/ux-channel+cxb")

    def test_intent_roundtrip(self):
        doc = {
            "v": "1",
            "action": "Cart.add",
            "args": {"sku": "a", "n": 2},
            "cap": "tok",
            "request_id": "rid",
        }
        raw = encode_cxb(doc)
        self.assertTrue(is_cxb(raw))
        self.assertEqual(decode_cxb(raw)["action"], "Cart.add")
        self.assertEqual(decode_cxb(raw)["args"]["sku"], "a")

    def test_result_roundtrip(self):
        doc = _result_many()
        out = decode_cxb(encode_cxb(doc))
        self.assertTrue(out["ok"])
        self.assertEqual(len(out["ops"]), len(doc["ops"]))
        self.assertEqual(out["ops"][0]["op"], "toast")
        self.assertEqual(out["ops"][-1]["op"], "morph")

    def test_denser_than_json_and_msgpack_on_repeated_ops(self):
        doc = _result_many()
        cxb = encode_cxb(doc)
        js = json.dumps(doc, separators=(",", ":")).encode()
        try:
            import msgpack

            mp = msgpack.packb(doc, use_bin_type=True)
        except ImportError:
            mp = js
        # Domain codec must beat generic JSON; with interning+zlib beat msgpack too
        self.assertLess(len(cxb), len(js))
        self.assertLess(len(cxb), len(mp))

    def test_error_result(self):
        doc = {
            "v": "1",
            "ok": False,
            "ops": [],
            "error": {"code": "validation", "message": "bad", "fields": {"n": ["int"]}},
            "meta": {},
        }
        out = decode_cxb(encode_cxb(doc))
        self.assertFalse(out["ok"])
        self.assertEqual(out["error"]["code"], "validation")

    def test_wire_configure_cxb(self):
        configure_wire(format="cxb")
        doc = {"v": "1", "ok": True, "ops": [{"op": "toast", "message": "x", "level": "info"}]}
        blob = encode(doc)
        self.assertEqual(blob.format, "cxb")
        self.assertEqual(blob.media_type, MEDIA_TYPES["cxb"])
        self.assertEqual(decode(blob.data)["ops"][0]["message"], "x")

    def test_http_accept_cxb(self):
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        from ux_channel import ChannelConfig, Result, toast
        from ux_channel.asgi.fastapi import mount_channel
        from ux_channel.registry import ActionRegistry

        cfg = ChannelConfig.development(
            secret="dev-secret-key-32chars-minimum!!!!", rate_limit_per_minute=0
        )
        app = FastAPI()
        reg = ActionRegistry.from_config(cfg)

        @reg.action("Cxb.ping", idempotent=True)
        def ping():
            return Result.success(toast("pong"), toast("pong"))

        mount_channel(app, reg, config=cfg)
        c = TestClient(app)
        cap = reg.sign("Cxb.ping", {})
        r = c.post(
            "/ux-channel/action",
            json={"v": "1", "action": "Cxb.ping", "args": {}, "cap": cap},
            headers={
                "X-Channel": "1",
                "Accept": "application/ux-channel+cxb",
            },
        )
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.headers.get("x-channel-wire"), "cxb")
        body = decode_cxb(r.content)
        self.assertTrue(body["ok"])
        self.assertGreaterEqual(len(body.get("ops") or []), 1)


if __name__ == "__main__":
    unittest.main()
