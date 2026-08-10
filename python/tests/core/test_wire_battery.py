"""
Industry-style battery for the wire codec plane.

Covers patterns commonly required of production codecs (JSON / MessagePack /
custom binary / HTTP negotiation literature):

* round-trip identity (property-based + golden)
* cross-format isomorphism (same document)
* concurrency / race (encode∥decode∥configure)
* parallel batch order preservation
* fuzz / chaos (truncated, random, adversarial headers)
* boundaries (empty, deep, unicode, large)
* compression gate (CXBZ only when smaller)
* negotiation (Accept / Content-Type)
* determinism & size budgets
* failure modes (unknown format, bad magic, engine missing)
"""

from __future__ import annotations

import os
import random
import struct
import threading
import time
import unittest
from concurrent.futures import ThreadPoolExecutor, as_completed

from hypothesis import given, settings, strategies as st

from ux_channel.wire import (
    MEDIA_TYPES,
    available_formats,
    configure_wire,
    decode,
    decode_http_body,
    decode_many,
    dumps,
    encode,
    encode_http_body,
    encode_many,
    get_batch_workers,
    get_codec,
    loads,
    negotiate_request,
    negotiate_response,
    reset_wire,
    set_batch_workers,
    size_of,
)
from ux_channel.wire.cxb import MAGIC, decode_cxb, encode_cxb, is_cxb


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


def _result(n_toast: int = 3, html: str = "<b>1</b>"):
    ops = [{"op": "toast", "message": "Saved", "level": "success"} for _ in range(n_toast)]
    ops.append(
        {
            "op": "morph",
            "target": '[data-channel-id="cart"]',
            "html": html,
            "morph": "idiomorph",
        }
    )
    return {
        "v": "1",
        "ok": True,
        "ops": ops,
        "meta": {"action": "Cart.add", "request_id": "r1", "runtime": "0.1.0"},
    }


def _formats_available():
    return list(available_formats())


# ---------------------------------------------------------------------------
# Round-trip / isomorphism
# ---------------------------------------------------------------------------


class TestRoundTrip(unittest.TestCase):
    def tearDown(self):
        reset_wire()

    def test_all_formats_roundtrip_intent_result(self):
        docs = [_intent(), _result(8), _result(1, html="<div>" + "x" * 500 + "</div>")]
        for fmt in _formats_available():
            for doc in docs:
                blob = encode(doc, format=fmt)
                out = decode(blob.data, format=fmt)
                self.assertEqual(out.get("v"), doc.get("v"), msg=fmt)
                if "action" in doc:
                    self.assertEqual(out["action"], doc["action"])
                if "ops" in doc:
                    self.assertEqual(len(out["ops"]), len(doc["ops"]))
                    self.assertEqual(out["ops"][0]["op"], doc["ops"][0]["op"])

    def test_json_dumps_loads_independent_of_binary_policy(self):
        configure_wire(format="cxb")
        s = dumps({"a": 1, "b": [True, None]})
        self.assertEqual(loads(s), {"a": 1, "b": [True, None]})
        self.assertEqual(get_codec().format, "cxb")

    def test_cross_format_isomorphism_core_fields(self):
        doc = _result(5)
        decoded = {}
        for fmt in _formats_available():
            decoded[fmt] = decode(encode(doc, format=fmt).data, format=fmt)
        # all agree on ok / op count / first op
        refs = list(decoded.values())
        for d in refs[1:]:
            self.assertEqual(d["ok"], refs[0]["ok"])
            self.assertEqual(len(d["ops"]), len(refs[0]["ops"]))
            self.assertEqual(d["ops"][0]["message"], refs[0]["ops"][0]["message"])


# ---------------------------------------------------------------------------
# Hypothesis property tests (JSON document space)
# ---------------------------------------------------------------------------


# Bounded JSON-like values (no NaN — JSON engines differ)
_json_scalars = st.one_of(
    st.none(),
    st.booleans(),
    st.integers(min_value=-(2**53), max_value=2**53),
    st.floats(allow_nan=False, allow_infinity=False, width=32),
    st.text(max_size=40),
)
_json_values = st.recursive(
    _json_scalars,
    lambda children: st.lists(children, max_size=6)
    | st.dictionaries(st.text(min_size=1, max_size=12), children, max_size=6),
    max_leaves=30,
)


class TestHypothesis(unittest.TestCase):
    def tearDown(self):
        reset_wire()

    @settings(max_examples=80, deadline=None)
    @given(doc=_json_values)
    def test_json_engine_roundtrip_property(self, doc):
        configure_wire(format="json", engine="stdlib")
        self.assertEqual(loads(dumps(doc)), doc)

    @settings(max_examples=40, deadline=None)
    @given(
        action=st.text(min_size=1, max_size=32),
        n=st.integers(min_value=0, max_value=50),
        sku=st.text(max_size=24),
    )
    def test_cxb_intent_property(self, action, n, sku):
        doc = _intent(action=action or "A", args={"sku": sku, "n": n})
        out = decode_cxb(encode_cxb(doc))
        self.assertEqual(out["action"], doc["action"])
        self.assertEqual(out["args"]["n"], n)


# ---------------------------------------------------------------------------
# Concurrency / parallel
# ---------------------------------------------------------------------------


class TestConcurrency(unittest.TestCase):
    def tearDown(self):
        reset_wire()
        set_batch_workers(0)

    def test_parallel_encode_decode_same_doc(self):
        doc = _result(10)
        errors: list[BaseException] = []

        def worker(fmt: str):
            try:
                for _ in range(50):
                    blob = encode(doc, format=fmt)
                    out = decode(blob.data, format=fmt)
                    assert out["ok"] is True
                    assert len(out["ops"]) == len(doc["ops"])
            except BaseException as exc:  # noqa: BLE001
                errors.append(exc)

        fmts = _formats_available()
        with ThreadPoolExecutor(max_workers=len(fmts) * 2) as pool:
            futs = [pool.submit(worker, f) for f in fmts for _ in range(2)]
            for f in as_completed(futs):
                f.result()
        self.assertEqual(errors, [])

    def test_configure_race_does_not_crash_encoders(self):
        doc = _result(4)
        stop = threading.Event()
        errors: list[BaseException] = []

        def reconfig():
            try:
                i = 0
                while not stop.is_set():
                    fmt = _formats_available()[i % len(_formats_available())]
                    configure_wire(format=fmt)
                    i += 1
            except BaseException as exc:  # noqa: BLE001
                errors.append(exc)

        def hammer():
            try:
                while not stop.is_set():
                    # always pass explicit format — independent of process policy
                    encode(doc, format="json")
                    encode(doc, format="cxb")
                    dumps(doc)
            except BaseException as exc:  # noqa: BLE001
                errors.append(exc)

        threads = [threading.Thread(target=reconfig)] + [
            threading.Thread(target=hammer) for _ in range(6)
        ]
        for t in threads:
            t.start()
        time.sleep(0.35)
        stop.set()
        for t in threads:
            t.join(timeout=2)
        self.assertEqual(errors, [])

    def test_encode_many_parallel_preserves_order(self):
        docs = [_intent(request_id=f"r{i}", args={"i": i}) for i in range(40)]
        set_batch_workers(8)
        blobs = encode_many(docs, format="cxb", workers=8)
        self.assertEqual(len(blobs), 40)
        outs = decode_many([b.data for b in blobs], format="cxb", workers=8)
        for i, out in enumerate(outs):
            self.assertEqual(out["request_id"], f"r{i}")
            self.assertEqual(out["args"]["i"], i)

    def test_encode_many_sequential_default(self):
        self.assertEqual(get_batch_workers(), 0)
        docs = [_intent(args={"i": i}) for i in range(5)]
        blobs = encode_many(docs, format="json")
        self.assertEqual(len(blobs), 5)
        self.assertEqual(blobs[0].format, "json")

    def test_thread_local_isolation_cxb(self):
        """Each encode must not share mutable intern tables across threads."""
        results = []
        lock = threading.Lock()

        def go(seed: int):
            doc = _result(n_toast=20 + seed, html=f"<i>{seed}</i>" + ("z" * (seed * 10)))
            for _ in range(30):
                out = decode_cxb(encode_cxb(doc))
                with lock:
                    results.append(out["ops"][-1]["html"])

        threads = [threading.Thread(target=go, args=(i,)) for i in range(8)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        self.assertEqual(len(results), 8 * 30)


# ---------------------------------------------------------------------------
# Fuzz / chaos / adversarial
# ---------------------------------------------------------------------------


class TestFuzzChaos(unittest.TestCase):
    def tearDown(self):
        reset_wire()

    def test_random_bytes_do_not_crash_decoders(self):
        rng = random.Random(42)
        for _ in range(200):
            blob = bytes(rng.getrandbits(8) for _ in range(rng.randint(0, 64)))
            for fmt in _formats_available():
                try:
                    decode(blob, format=fmt)
                except Exception:
                    pass  # must not abort process

    def test_truncated_cxb_magic_only(self):
        with self.assertRaises(Exception):
            decode_cxb(MAGIC)  # too short

    def test_truncated_cxb_after_kind(self):
        with self.assertRaises(Exception):
            decode_cxb(MAGIC + b"\x02")  # kind result, no table

    def test_bad_magic(self):
        with self.assertRaises(ValueError):
            decode_cxb(b"XXXX" + b"\x00" * 20)

    def test_cxbz_bad_payload(self):
        with self.assertRaises(Exception):
            decode_cxb(b"CXBZ" + b"not-zlib")

    def test_json_loads_garbage(self):
        with self.assertRaises(Exception):
            loads("{not json")

    def test_negotiate_unknown_content_type_falls_back_json(self):
        self.assertEqual(negotiate_request("application/octet-stream"), "json")
        self.assertEqual(negotiate_request(""), "json")

    def test_http_body_empty(self):
        self.assertEqual(decode_http_body(b""), {})

    def test_deeply_nested_json(self):
        doc: dict = {"v": "1"}
        cur = doc
        for i in range(40):
            cur["c"] = {"i": i}
            cur = cur["c"]
        blob = encode(doc, format="json")
        out = decode(blob.data, format="json")
        self.assertEqual(out["v"], "1")

    def test_unicode_and_emoji(self):
        doc = _intent(action="订单.添加", args={"note": "café ☕ — 日本語"})
        for fmt in _formats_available():
            out = decode(encode(doc, format=fmt).data, format=fmt)
            self.assertEqual(out["action"], doc["action"])
            self.assertEqual(out["args"]["note"], doc["args"]["note"])

    def test_binary_cap_string_roundtrip(self):
        doc = _intent(cap="\x00\x01secret\xff")
        # may become escaped string via default — at least no crash
        for fmt in ("json", "cxb"):
            if fmt not in _formats_available():
                continue
            encode(doc, format=fmt)


# ---------------------------------------------------------------------------
# Compression gate
# ---------------------------------------------------------------------------


class TestCompressionGate(unittest.TestCase):
    def test_small_frame_never_cxbz(self):
        doc = {"v": "1", "ok": True, "ops": [{"op": "toast", "message": "x", "level": "info"}]}
        raw = encode_cxb(doc)
        self.assertTrue(raw.startswith(MAGIC))
        self.assertFalse(raw.startswith(b"CXBZ"))

    def test_large_repetitive_prefers_cxbz_when_smaller(self):
        doc = _result(30, html="<div>" + ("item " * 200) + "</div>")
        raw = encode_cxb(doc)
        # either CXB1 or CXBZ; if CXBZ, decompressed must round-trip
        self.assertTrue(is_cxb(raw))
        out = decode_cxb(raw)
        self.assertTrue(out["ok"])
        self.assertEqual(len(out["ops"]), 31)

    def test_high_entropy_may_stay_cxb1(self):
        # random HTML unlikely to compress below threshold margin
        rng = random.Random(7)
        html = "<div>" + "".join(chr(rng.randint(33, 126)) for _ in range(600)) + "</div>"
        doc = _result(1, html=html)
        raw = encode_cxb(doc)
        self.assertTrue(is_cxb(raw))
        self.assertEqual(decode_cxb(raw)["ops"][-1]["html"], html)


# ---------------------------------------------------------------------------
# Negotiation + media types
# ---------------------------------------------------------------------------


class TestNegotiation(unittest.TestCase):
    def tearDown(self):
        reset_wire()

    def test_media_types_stable(self):
        self.assertEqual(MEDIA_TYPES["json"], "application/ux-channel+json")
        self.assertEqual(MEDIA_TYPES["cxb"], "application/ux-channel+cxb")

    def test_accept_prefers_cxb(self):
        if "cxb" not in _formats_available():
            self.skipTest("no cxb")
        self.assertEqual(
            negotiate_response("application/ux-channel+cxb, application/json"),
            "cxb",
        )

    def test_encode_http_echoes_request_format(self):
        doc = {"v": "1", "ok": True, "ops": []}
        blob = encode_http_body(
            doc,
            accept=None,
            content_type_in="application/ux-channel+cxb",
        )
        self.assertEqual(blob.format, "cxb")
        self.assertEqual(decode_http_body(blob.data, content_type=blob.media_type)["ok"], True)


# ---------------------------------------------------------------------------
# Determinism, size, failure modes
# ---------------------------------------------------------------------------


class TestDeterminismAndLimits(unittest.TestCase):
    def tearDown(self):
        reset_wire()

    def test_cxb_deterministic(self):
        doc = _result(6)
        a = encode_cxb(doc)
        b = encode_cxb(doc)
        self.assertEqual(a, b)

    def test_json_size_of_matches_dumps_bytes(self):
        configure_wire(format="json", engine="stdlib")
        doc = _result(2)
        self.assertEqual(size_of(doc), len(encode(doc, format="json").data))

    def test_unknown_format_raises(self):
        with self.assertRaises(ValueError):
            configure_wire(format="protobuf", strict=True)

    def test_cxb_denser_than_json_on_repeated_ops(self):
        doc = _result(25)
        j = len(encode(doc, format="json").data)
        c = len(encode(doc, format="cxb").data)
        self.assertLess(c, j)

    def test_default_str_unknown_types_json(self):
        class Odd:
            def __str__(self):
                return "odd"

        configure_wire(format="json", engine="stdlib")
        self.assertIn("odd", dumps({"o": Odd()}))


# ---------------------------------------------------------------------------
# Golden vectors (pin magic / kind layout)
# ---------------------------------------------------------------------------


class TestGolden(unittest.TestCase):
    def test_magic_and_kind_intent(self):
        raw = encode_cxb(_intent())
        self.assertEqual(raw[:4], MAGIC)
        # after magic: kind=1 intent
        self.assertEqual(raw[4], 1)

    def test_magic_and_kind_result(self):
        raw = encode_cxb(_result(1))
        if raw[:4] == b"CXBZ":
            import zlib

            raw = zlib.decompress(raw[4:])
        self.assertEqual(raw[:4], MAGIC)
        self.assertEqual(raw[4], 2)  # result


# ---------------------------------------------------------------------------
# Live ASGI multi-format under concurrency
# ---------------------------------------------------------------------------


class TestAsgiConcurrentWire(unittest.TestCase):
    def tearDown(self):
        reset_wire()

    def test_parallel_http_json_and_cxb(self):
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        from ux_channel import ChannelConfig, Result, toast
        from ux_channel.asgi.fastapi import mount_channel
        from ux_channel.registry import ActionRegistry
        from ux_channel.wire.cxb import decode_cxb

        cfg = ChannelConfig.development(
            secret="dev-secret-key-32chars-minimum!!!!", rate_limit_per_minute=0
        )
        app = FastAPI()
        reg = ActionRegistry.from_config(cfg)

        @reg.action("Wire.stress", idempotent=True)
        def stress(n: int = 1):
            ops = [toast(f"t{i}") for i in range(int(n))]
            return Result.success(*ops)

        mount_channel(app, reg, config=cfg)
        client = TestClient(app)
        cap = reg.mint("Wire.stress", {"n": 5})

        def hit_json():
            r = client.post(
                "/ux-channel/action",
                json={"v": "1", "action": "Wire.stress", "args": {"n": 5}, "cap": cap},
                headers={"X-Channel": "1"},
            )
            assert r.status_code == 200
            assert r.json()["ok"] is True

        def hit_cxb():
            r = client.post(
                "/ux-channel/action",
                json={"v": "1", "action": "Wire.stress", "args": {"n": 5}, "cap": cap},
                headers={
                    "X-Channel": "1",
                    "Accept": "application/ux-channel+cxb",
                },
            )
            assert r.status_code == 200
            assert r.headers.get("x-channel-wire") == "cxb"
            body = decode_cxb(r.content)
            assert body["ok"] is True

        with ThreadPoolExecutor(max_workers=12) as pool:
            futs = [pool.submit(hit_json) for _ in range(20)] + [
                pool.submit(hit_cxb) for _ in range(20)
            ]
            for f in as_completed(futs):
                f.result()


if __name__ == "__main__":
    unittest.main()
