"""Wire codec plane: formats, engines, negotiate, opt-in binary upgrades."""

from __future__ import annotations

import os
import unittest

from ux_channel.wire import (
    MEDIA_TYPES,
    available_engines,
    available_formats,
    configure_wire,
    decode,
    dumps,
    dumps_bytes,
    encode,
    get_codec,
    get_policy,
    loads,
    reset_wire,
    size_of,
)
from ux_channel.wire.negotiate import (
    decode_http_body,
    encode_http_body,
    negotiate_request,
    negotiate_response,
    parse_accept,
)


class TestWireDefaults(unittest.TestCase):
    def tearDown(self):
        reset_wire()

    def test_default_format_json(self):
        reset_wire()
        self.assertEqual(get_policy().format, "json")
        self.assertIn(get_codec().engine, available_engines())
        self.assertEqual(get_codec().media_type, MEDIA_TYPES["json"])

    def test_json_roundtrip_engines(self):
        for eng in available_engines():
            configure_wire(format="json", engine=eng)
            obj = {"v": "1", "ok": True, "ops": [{"op": "toast", "message": "hi"}], "n": 3}
            self.assertEqual(loads(dumps(obj)), obj)
            self.assertEqual(loads(dumps_bytes(obj)), obj)
            blob = encode(obj)
            self.assertEqual(blob.format, "json")
            self.assertEqual(decode(blob.data, format="json"), obj)

    def test_pretty_opt_in(self):
        configure_wire(format="json", engine="stdlib")
        self.assertIn("\n", dumps({"a": 1}, pretty=True))

    def test_dumps_always_json_even_if_policy_binary(self):
        if "msgpack" not in available_formats():
            self.skipTest("msgpack not installed")
        configure_wire(format="msgpack")
        self.assertEqual(get_policy().format, "msgpack")
        # dumps still JSON for DX / stores that want text
        s = dumps({"x": 1})
        self.assertIsInstance(s, str)
        self.assertEqual(loads(s), {"x": 1})
        # encode uses active binary format
        blob = encode({"x": 1})
        self.assertEqual(blob.format, "msgpack")
        self.assertEqual(blob.media_type, MEDIA_TYPES["msgpack"])
        self.assertEqual(decode(blob.data), {"x": 1})

    def test_msgpack_opt_in(self):
        if "msgpack" not in available_formats():
            self.skipTest("msgpack not installed")
        configure_wire(format="msgpack")
        obj = {"v": "1", "ok": True, "ops": []}
        blob = encode(obj)
        self.assertEqual(decode(blob.data, media_type=blob.media_type), obj)

    def test_force_unknown_engine_raises(self):
        with self.assertRaises(ValueError):
            configure_wire(engine="not-a-real-engine", strict=True)
        # Missing engine: soft falls back; strict raises
        from ux_channel.wire import available_engines
        if "ujson" not in available_engines():
            configure_wire(format="json", engine="ujson")  # soft → available engine
            self.assertIn(get_codec().engine, available_engines())
            with self.assertRaises(RuntimeError):
                configure_wire(format="json", engine="ujson", strict=True)

    def test_unknown_format_raises(self):
        with self.assertRaises(ValueError):
            configure_wire(format="protobuf", strict=True)

    def test_size_of_is_json(self):
        configure_wire(format="json", engine="stdlib")
        self.assertEqual(size_of({"a": 1}), len(dumps_bytes({"a": 1})))

    def test_env_wire_format(self):
        if "msgpack" not in available_formats():
            self.skipTest("msgpack not installed")
        os.environ["UX_CHANNEL_WIRE"] = "msgpack"
        try:
            c = reset_wire()
            self.assertEqual(c.format, "msgpack")
        finally:
            os.environ.pop("UX_CHANNEL_WIRE", None)
            reset_wire()

    def test_configure_wire_engine_only(self):
        configure_wire(engine="stdlib")
        self.assertEqual(get_codec().engine, "stdlib")


class TestNegotiate(unittest.TestCase):
    def tearDown(self):
        reset_wire()

    def test_parse_accept(self):
        self.assertEqual(
            parse_accept("application/ux-channel+msgpack, application/json"),
            ["msgpack", "json"],
        )

    def test_negotiate_request_content_type(self):
        self.assertEqual(
            negotiate_request("application/ux-channel+json; charset=utf-8"), "json"
        )
        if "msgpack" in available_formats():
            self.assertEqual(
                negotiate_request("application/ux-channel+msgpack"), "msgpack"
            )
        self.assertEqual(negotiate_request(None), "json")

    def test_http_body_roundtrip_json(self):
        configure_wire(format="json", engine="stdlib")
        obj = {"v": "1", "action": "Ping", "args": {}}
        blob = encode_http_body(obj, accept="application/ux-channel+json")
        self.assertEqual(blob.format, "json")
        self.assertEqual(
            decode_http_body(blob.data, content_type=blob.media_type), obj
        )

    def test_http_body_msgpack_when_accepted(self):
        if "msgpack" not in available_formats():
            self.skipTest("msgpack not installed")
        obj = {"v": "1", "ok": True, "ops": []}
        blob = encode_http_body(
            obj, accept="application/ux-channel+msgpack"
        )
        self.assertEqual(blob.format, "msgpack")
        self.assertEqual(decode_http_body(blob.data, content_type=blob.media_type), obj)

    def test_echo_request_format(self):
        if "msgpack" not in available_formats():
            self.skipTest("msgpack not installed")
        obj = {"v": "1", "ok": True}
        # No Accept, but request was msgpack → echo
        blob = encode_http_body(
            obj,
            accept=None,
            content_type_in="application/ux-channel+msgpack",
        )
        self.assertEqual(blob.format, "msgpack")


class TestAsgiWire(unittest.TestCase):
    def tearDown(self):
        reset_wire()

    def test_action_json_default(self):
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        from ux_channel import Channel, ChannelConfig, Result, toast
        from ux_channel.asgi.fastapi import mount_channel
        from ux_channel.registry import ActionRegistry

        cfg = ChannelConfig.development(
            secret="dev-secret-key-32chars-minimum!!!!", rate_limit_per_minute=0
        )
        app = FastAPI()
        reg = ActionRegistry.from_config(cfg)

        @reg.action("W.ping", idempotent=True)
        def ping():
            return Result.success(toast("pong"))

        mount_channel(app, reg, config=cfg)
        c = TestClient(app)
        cap = reg.sign("W.ping", {})
        r = c.post(
            "/ux-channel/action",
            json={"v": "1", "action": "W.ping", "args": {}, "cap": cap},
            headers={"X-Channel": "1"},
        )
        self.assertEqual(r.status_code, 200)
        self.assertIn("json", r.headers.get("content-type", ""))
        self.assertTrue(r.json()["ok"])
        self.assertEqual(r.headers.get("x-channel-wire"), "json")

    def test_action_msgpack_accept(self):
        if "msgpack" not in available_formats():
            self.skipTest("msgpack not installed")
        import msgpack
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

        @reg.action("W.bin", idempotent=True)
        def bin_():
            return Result.success(toast("bin"))

        mount_channel(app, reg, config=cfg)
        c = TestClient(app)
        cap = reg.sign("W.bin", {})
        body = msgpack.packb(
            {"v": "1", "action": "W.bin", "args": {}, "cap": cap}, use_bin_type=True
        )
        r = c.post(
            "/ux-channel/action",
            content=body,
            headers={
                "X-Channel": "1",
                "Content-Type": "application/ux-channel+msgpack",
                "Accept": "application/ux-channel+msgpack",
            },
        )
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.headers.get("x-channel-wire"), "msgpack")
        data = msgpack.unpackb(r.content, raw=False)
        self.assertTrue(data["ok"])


if __name__ == "__main__":
    unittest.main()
