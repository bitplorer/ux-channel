# Copyright (c) 2026 UX-CHANNEL
"""
Wire codec conformance + live behaviour suite.

Patterned after test categories used by production codecs at scale
(msgpack-python, protobuf conformance, orjson / JSON RFCs), adapted to
ux-channel's Intent/Result + multi-format plane.

Layers
------
A. Clarity         — one format name, stable media type, readable errors
B. Type matrix     — scalars / containers / edge numbers (msgpack-style)
C. Domain ops      — every Result op builder + freeform future ops
D. Properties      — Hypothesis round-trip / safety (in sibling modules too)
E. Wire integrity  — CRC, CXBZ, determinism, unknown-field preserve
F. Negotiation     — HTTP Content-Type / Accept (proto-style content rules)
G. Live ASGI       — real HTTP encode/decode under concurrency (billions-of-
                     msgs style soak, short budget for CI)
H. Intention       — channel-specific: complete recovery, browser JSON floor
"""

from __future__ import annotations

import math
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor, as_completed

from hypothesis import given, settings, strategies as st

from ux_channel.wire import (
    MEDIA_TYPES,
    available_formats,
    configure_wire,
    decode,
    decode_http_body,
    dumps,
    encode,
    encode_http_body,
    get_codec,
    loads,
    negotiate_request,
    negotiate_response,
    reset_wire,
    try_decode,
)
from ux_channel.wire.cxb import (
    FORMAT_NAME,
    MAGIC,
    MAGIC_Z,
    MEDIA_TYPE,
    decode_cxb,
    encode_cxb,
    is_cxb,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _intent(**over):
    base = {
        "v": "1",
        "action": "Cart.add",
        "args": {"sku": "a", "n": 1},
        "cap": "c" * 16,
        "request_id": "r1",
    }
    base.update(over)
    return base


def _result(ops=None):
    return {
        "v": "1",
        "ok": True,
        "ops": ops
        or [
            {"op": "toast", "message": "ok", "level": "info"},
            {
                "op": "morph",
                "target": '[data-channel-id="c"]',
                "html": "<b>1</b>",
                "morph": "idiomorph",
            },
        ],
        "meta": {"action": "Cart.add", "request_id": "r1"},
    }


def _formats():
    return list(available_formats())


# ===========================================================================
# A. Clarity
# ===========================================================================


class TestClarity(unittest.TestCase):
    def tearDown(self):
        reset_wire()

    def test_single_format_name_cxb(self):
        self.assertEqual(FORMAT_NAME, "cxb")
        self.assertEqual(MEDIA_TYPES["cxb"], MEDIA_TYPE)
        self.assertEqual(MEDIA_TYPE, "application/ux-channel+cxb")

    def test_no_secret_format_aliases(self):
        configure_wire(format="json")
        configure_wire(format="channelbin")  # soft floor, not alias→cxb
        self.assertEqual(get_codec().format, "json")
        with self.assertRaises(ValueError):
            configure_wire(format="channel", strict=True)

    def test_available_formats_are_real_names_only(self):
        names = set(available_formats())
        self.assertIn("json", names)
        self.assertIn("cxb", names)
        self.assertNotIn("channelbin", names)
        self.assertNotIn("channel", names)

    def test_error_messages_name_the_problem(self):
        with self.assertRaises(ValueError) as cm:
            decode_cxb(b"NOPE")
        self.assertIn("CXB", str(cm.exception).upper() + str(cm.exception))


# ===========================================================================
# B. Type matrix (msgpack / JSON codec style)
# ===========================================================================


class TestTypeMatrix(unittest.TestCase):
    """Scalars + containers that production codecs always cover."""

    CASES = [
        None,
        True,
        False,
        0,
        1,
        -1,
        127,
        128,
        255,
        256,
        2**31 - 1,
        -(2**31),
        2**53 - 1,  # JSON-safe int max
        0.0,
        -0.0,
        1.5,
        math.pi,
        "",
        "a",
        "hello",
        "café",
        "日本語",
        "emoji 🎉",
        "\n\t\r",
        [],
        [1, 2, 3],
        [None, True, "x"],
        {},
        {"a": 1},
        {"nested": {"b": [1, {"c": False}]}},
    ]

    def test_json_type_matrix(self):
        for val in self.CASES:
            doc = {"v": "1", "action": "T", "args": {"x": val}}
            out = decode(encode(doc, format="json").data, format="json")
            # -0.0 may normalize
            if isinstance(val, float) and val == 0.0:
                self.assertEqual(out["args"]["x"], 0.0)
            else:
                self.assertEqual(out["args"]["x"], val, msg=repr(val))

    def test_cxb_type_matrix_in_args_and_meta(self):
        for val in self.CASES:
            doc = {
                "v": "1",
                "ok": True,
                "ops": [{"op": "probe", "value": val, "payload": {"x": val}}],
                "meta": {"sample": val} if not isinstance(val, (list, dict)) or val == {} or val == [] else {"n": 1},
            }
            out = decode_cxb(encode_cxb(doc))
            self.assertEqual(out["ops"][0]["value"], val, msg=repr(val))

    def test_msgpack_type_matrix_if_present(self):
        if "msgpack" not in _formats():
            self.skipTest("msgpack not installed")
        for val in self.CASES:
            doc = {"v": "1", "action": "T", "args": {"x": val}}
            out = decode(encode(doc, format="msgpack").data, format="msgpack")
            if isinstance(val, float) and val == 0.0:
                self.assertEqual(out["args"]["x"], 0.0)
            else:
                self.assertEqual(out["args"]["x"], val)


# ===========================================================================
# C / E. Integrity + domain
# ===========================================================================


class TestIntegrity(unittest.TestCase):
    def test_cxb_deterministic(self):
        doc = _result()
        self.assertEqual(encode_cxb(doc), encode_cxb(doc))

    def test_crc_reject(self):
        raw = encode_cxb(_result())
        if raw[:4] == MAGIC_Z:
            self.skipTest("compressed")
        bad = raw[:-1] + bytes([raw[-1] ^ 0xFF])
        with self.assertRaises(ValueError):
            decode_cxb(bad)

    def test_unknown_op_fields_preserved(self):
        """protobuf-style: unknown fields must not be dropped."""
        op = {
            "op": "future.x",
            "brand_new_field": 42,
            "nested": {"k": [1, 2]},
            "meta": {"trace": "t"},
        }
        out = decode_cxb(encode_cxb({"v": "1", "ok": True, "ops": [op]}))
        self.assertEqual(out["ops"][0], op)

    def test_is_cxb_magic(self):
        raw = encode_cxb(_result())
        self.assertTrue(is_cxb(raw))
        self.assertFalse(is_cxb(b"{}"))
        self.assertFalse(is_cxb(b""))


# ===========================================================================
# D. Properties (local + intentional channel docs)
# ===========================================================================


_json_vals = st.recursive(
    st.one_of(
        st.none(),
        st.booleans(),
        st.integers(min_value=-(2**53) + 1, max_value=2**53 - 1),
        st.floats(allow_nan=False, allow_infinity=False, width=32),
        st.text(max_size=40),
    ),
    lambda c: st.lists(c, max_size=5)
    | st.dictionaries(st.text(min_size=1, max_size=10), c, max_size=5),
    max_leaves=25,
)


class TestProperties(unittest.TestCase):
    def tearDown(self):
        reset_wire()

    @settings(max_examples=80, deadline=None)
    @given(args=st.dictionaries(st.text(min_size=1, max_size=8), _json_vals, max_size=5))
    def test_intent_args_roundtrip_all_formats(self, args):
        doc = _intent(args=args)
        for fmt in _formats():
            out = decode(encode(doc, format=fmt).data, format=fmt)
            self.assertEqual(out["action"], "Cart.add")
            self.assertEqual(out["args"], args)

    @settings(max_examples=40, deadline=None)
    @given(
        message=st.text(max_size=60),
        level=st.sampled_from(["info", "success", "warning", "error"]),
    )
    def test_toast_op_property(self, message, level):
        doc = _result(
            ops=[{"op": "toast", "message": message, "level": level}]
        )
        out = decode_cxb(encode_cxb(doc))
        self.assertEqual(out["ops"][0]["message"], message)
        self.assertEqual(out["ops"][0]["level"], level)

    @settings(max_examples=100, deadline=None)
    @given(data=st.binary(max_size=128))
    def test_try_decode_total(self, data):
        for fmt in _formats():
            try_decode(data, format=fmt, default=None)


# ===========================================================================
# F. Negotiation (content-type rules)
# ===========================================================================


class TestNegotiation(unittest.TestCase):
    def tearDown(self):
        reset_wire()

    def test_request_prefers_content_type(self):
        self.assertEqual(
            negotiate_request("application/ux-channel+cxb"), "cxb"
        )
        self.assertEqual(negotiate_request("application/json"), "json")
        self.assertEqual(negotiate_request(None), "json")
        self.assertEqual(negotiate_request("text/plain"), "json")

    def test_response_accept_order(self):
        self.assertEqual(
            negotiate_response(
                "application/ux-channel+cxb, application/json"
            ),
            "cxb",
        )
        self.assertEqual(negotiate_response("application/json"), "json")

    def test_http_body_roundtrip_each_format(self):
        doc = _result()
        for fmt in _formats():
            mt = MEDIA_TYPES[fmt]
            blob = encode_http_body(doc, accept=mt)
            self.assertEqual(blob.format, fmt)
            back = decode_http_body(blob.data, content_type=blob.media_type)
            self.assertEqual(back["ok"], True)
            self.assertEqual(len(back["ops"]), len(doc["ops"]))


# ===========================================================================
# H. Intention (channel-specific)
# ===========================================================================


class TestIntention(unittest.TestCase):
    def tearDown(self):
        reset_wire()

    def test_browser_default_is_json(self):
        reset_wire()
        self.assertEqual(get_codec().format, "json")
        s = dumps({"ok": True})
        self.assertIsInstance(s, str)
        self.assertEqual(loads(s), {"ok": True})

    def test_complete_recovers_mislabeled_cxb(self):
        blob = encode(_result(), format="cxb")
        out = decode(blob.data, format="json", complete=True)
        self.assertTrue(out["ok"])

    def test_empty_body_is_empty_object(self):
        self.assertEqual(decode(b""), {})
        self.assertEqual(decode_http_body(b""), {})

    def test_encode_complete_always_returns_bytes(self):
        blob = encode(_result(), format="cxb", complete=True)
        self.assertIsInstance(blob.data, (bytes, bytearray))
        self.assertTrue(blob.media_type)


# ===========================================================================
# G. Live ASGI behaviour (production-style)
# ===========================================================================


class TestLiveAsgi(unittest.TestCase):
    """Real HTTP path — like load tests on msgpack/protobuf HTTP services."""

    def tearDown(self):
        reset_wire()

    def _client(self):
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        from ux_channel import ChannelConfig, Result, toast, morph
        from ux_channel.asgi.fastapi import mount_channel
        from ux_channel.registry import ActionRegistry

        cfg = ChannelConfig.development(
            secret="dev-secret-key-32chars-minimum!!!!",
            rate_limit_per_minute=0,
        )
        app = FastAPI()
        reg = ActionRegistry.from_config(cfg)

        @reg.action("Live.ping", idempotent=True)
        def ping(n: int = 1, note: str = ""):
            ops = [toast(f"n={n}:{note}", level="info")]
            if n > 0:
                ops.append(
                    morph(
                        '[data-channel-id="live"]',
                        f"<span data-channel-id=\"live\">{n}</span>",
                    )
                )
            return Result.success(*ops)

        mount_channel(app, reg, config=cfg)
        client = TestClient(app)
        return client, reg

    def _post(self, client, reg, *, n=1, note="x", accept=None):
        args = {"n": n, "note": note}
        cap = reg.sign("Live.ping", args)
        headers = {"X-Channel": "1"}
        if accept:
            headers["Accept"] = accept
        return client.post(
            "/ux-channel/action",
            json={
                "v": "1",
                "action": "Live.ping",
                "args": args,
                "cap": cap,
            },
            headers=headers,
        )

    def test_live_json_action(self):
        client, reg = self._client()
        r = self._post(client, reg, n=3, note="hi")
        self.assertEqual(r.status_code, 200, r.text)
        body = r.json()
        self.assertTrue(body["ok"])
        self.assertGreaterEqual(len(body["ops"]), 1)
        self.assertEqual(r.headers.get("x-channel-wire"), "json")

    def test_live_cxb_accept(self):
        client, reg = self._client()
        r = self._post(
            client, reg, n=2, note="cxb",
            accept="application/ux-channel+cxb",
        )
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual(r.headers.get("x-channel-wire"), "cxb")
        body = decode_cxb(r.content)
        self.assertTrue(body["ok"])
        self.assertEqual(body["ops"][0]["op"], "toast")

    def test_live_concurrent_json_and_cxb(self):
        client, reg = self._client()
        errors: list[str] = []

        def hit(fmt: str):
            try:
                accept = "application/ux-channel+cxb" if fmt == "cxb" else None
                r = self._post(client, reg, n=1, note=fmt, accept=accept)
                assert r.status_code == 200, r.text
                body = decode_cxb(r.content) if fmt == "cxb" else r.json()
                assert body["ok"] is True
            except Exception as exc:  # noqa: BLE001
                errors.append(repr(exc))

        with ThreadPoolExecutor(max_workers=16) as pool:
            futs = []
            for _ in range(30):
                futs.append(pool.submit(hit, "json"))
                futs.append(pool.submit(hit, "cxb"))
            for f in as_completed(futs):
                f.result()
        self.assertEqual(errors, [])

    def test_live_mislabeled_recovery_still_acts(self):
        """Browser JSON floor — Content-Type application/json always works."""
        client, reg = self._client()
        r = self._post(client, reg, n=1, note="browser")
        self.assertEqual(r.status_code, 200, r.text)
        self.assertTrue(r.json()["ok"])


class TestLiveConcurrentCodec(unittest.TestCase):
    """In-process concurrent encode/decode like multi-tenant gateways."""

    def test_parallel_mixed_formats(self):
        doc = _result(
            ops=[
                {"op": "toast", "message": "m", "level": "info"},
            ]
            * 10
            + [
                {
                    "op": "plugin.x",
                    "payload": {"i": i},
                    "meta": {"t": i},
                }
                for i in range(5)
            ]
        )
        errors: list[str] = []

        def worker(fmt: str, n: int):
            try:
                for i in range(n):
                    blob = encode(doc, format=fmt)
                    out = decode(blob.data, format=fmt)
                    assert out["ok"] is True
                    assert len(out["ops"]) == len(doc["ops"])
            except Exception as exc:  # noqa: BLE001
                errors.append(f"{fmt}:{exc!r}")

        threads = []
        for fmt in _formats():
            for _ in range(4):
                threads.append(
                    threading.Thread(target=worker, args=(fmt, 40))
                )
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        self.assertEqual(errors, [])


if __name__ == "__main__":
    unittest.main()
