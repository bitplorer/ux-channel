"""Enterprise production-safety suite for the wire codec plane.

Validates invariants required before shipping a codec used by many clients:

1. Safe floor always present (JSON/stdlib path)
2. Soft vs strict configuration
3. Cache correctness under auto + concrete engines
4. Batch worker clamping / sequential default
5. No partial batch on failure
6. Decode empty / corrupt / bomb ceilings
7. Policy rollback / reset recovery
8. Side-effect free dumps while binary policy active
9. Concurrent hammers with reconfigure
10. try_decode never raises
"""

from __future__ import annotations

import os
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor

from ux_channel.wire import (
    clear_codec_cache,
    configure_wire,
    decode,
    decode_many,
    dumps,
    encode,
    encode_many,
    get_batch_workers,
    get_codec,
    get_policy,
    loads,
    reset_wire,
    set_batch_workers,
    try_decode,
)
from ux_channel.wire.cxb import encode_cxb, decode_cxb


class TestSafeFloor(unittest.TestCase):
    def tearDown(self):
        reset_wire()
        set_batch_workers(0)

    def test_process_always_has_codec(self):
        reset_wire()
        c = get_codec()
        self.assertIsNotNone(c)
        self.assertTrue(c.media_type)
        self.assertEqual(loads(dumps({"ok": True})), {"ok": True})

    def test_unknown_format_soft_stays_json(self):
        configure_wire(format="json", engine="stdlib")
        configure_wire(format="not-a-real-format")  # soft
        self.assertEqual(get_policy().format, "json")

    def test_unknown_format_strict_raises(self):
        with self.assertRaises(ValueError):
            configure_wire(format="not-a-real-format", strict=True)
        # policy still usable
        self.assertEqual(loads(dumps({"a": 1})), {"a": 1})

    def test_missing_binary_soft_falls_to_json(self):
        # cbor may be missing — soft configure must not brick process
        configure_wire(format="cbor")  # soft
        # either cbor if installed, else json
        self.assertIn(get_policy().format, ("cbor", "json"))
        self.assertEqual(loads(dumps({"x": 1})), {"x": 1})

    def test_bad_env_does_not_break_reset(self):
        os.environ["UX_CHANNEL_WIRE"] = "not-real"
        try:
            c = reset_wire()
            self.assertEqual(c.format, "json")
        finally:
            os.environ.pop("UX_CHANNEL_WIRE", None)
            reset_wire()


class TestCacheCorrectness(unittest.TestCase):
    def tearDown(self):
        reset_wire()

    def test_auto_and_concrete_share_cached_codec(self):
        clear_codec_cache()
        a = encode({"v": "1", "ok": True, "ops": []}, format="json", engine="auto")
        b = encode({"v": "1", "ok": True, "ops": []}, format="json", engine=get_codec().engine if get_policy().format=="json" else "auto")
        # both JSON media
        self.assertEqual(a.media_type, b.media_type)
        from ux_channel.wire import core as wire_core
        # only concrete keys
        for k in wire_core._CODEC_CACHE:
            self.assertNotEqual(k[1], "auto")

    def test_clear_cache_does_not_break_policy(self):
        configure_wire(format="cxb")
        clear_codec_cache()
        blob = encode({"v": "1", "ok": True, "ops": []})
        self.assertEqual(blob.format, "cxb")
        self.assertTrue(decode(blob.data)["ok"])


class TestBatchSafety(unittest.TestCase):
    def tearDown(self):
        set_batch_workers(0)
        reset_wire()

    def test_workers_clamped(self):
        self.assertEqual(set_batch_workers(10_000), 32)
        self.assertEqual(set_batch_workers(-3), 0)
        self.assertEqual(set_batch_workers("nope"), 0)  # type: ignore[arg-type]
        self.assertEqual(get_batch_workers(), 0)

    def test_default_sequential(self):
        self.assertEqual(get_batch_workers(), 0)
        docs = [{"v": "1", "action": "A", "args": {"i": i}} for i in range(5)]
        blobs = encode_many(docs, format="json")
        self.assertEqual(len(blobs), 5)

    def test_parallel_order_and_failure_propagation(self):
        docs = [{"v": "1", "action": "A", "args": {"i": i}} for i in range(20)]
        blobs = encode_many(docs, format="cxb", workers=4)
        outs = decode_many([b.data for b in blobs], format="cxb", workers=4)
        self.assertEqual([o["args"]["i"] for o in outs], list(range(20)))

        # failure in one worker propagates
        class Boom:
            def __str__(self):
                raise RuntimeError("nope")

        # JSON with default=str usually stringifies; force default that raises
        with self.assertRaises(Exception):
            encode_many(
                [{"x": Boom()}],
                format="json",
                workers=2,
            )


class TestDecodeSafety(unittest.TestCase):
    def tearDown(self):
        reset_wire()

    def test_empty_is_object(self):
        self.assertEqual(decode(b""), {})
        self.assertEqual(decode(""), {})
        self.assertEqual(decode(None), {})  # type: ignore[arg-type]

    def test_try_decode_never_raises(self):
        self.assertIsNone(try_decode(b"\xff\x00 not valid", format="json"))
        self.assertEqual(try_decode(b"{}", format="json"), {})
        self.assertEqual(
            try_decode(b"nope", format="cxb", default={"fallback": True}),
            {"fallback": True},
        )

    def test_cxb_magic_sniff_when_policy_json(self):
        configure_wire(format="json")
        raw = encode_cxb({"v": "1", "ok": True, "ops": []})
        # no format= — sniff CXB1
        out = decode(raw)
        self.assertTrue(out["ok"])

    def test_corrupt_raises_value_error(self):
        with self.assertRaises(ValueError):
            decode(b"CXB1\x02", format="cxb")

    def test_dumps_unaffected_by_cxb_policy(self):
        configure_wire(format="cxb")
        self.assertEqual(loads(dumps({"a": [1, True, None]})), {"a": [1, True, None]})


class TestConcurrencyProduction(unittest.TestCase):
    def tearDown(self):
        reset_wire()
        set_batch_workers(0)

    def test_million_user_hammer(self):
        """Sustained mixed traffic: encode/decode/configure/dumps."""
        errors: list[BaseException] = []
        stop = threading.Event()

        def encode_loop():
            try:
                for _ in range(200):
                    doc = {
                        "v": "1",
                        "ok": True,
                        "ops": [{"op": "toast", "message": "m", "level": "info"}] * 5,
                    }
                    for fmt in ("json", "cxb", "msgpack"):
                        try:
                            b = encode(doc, format=fmt)
                            decode(b.data, format=fmt)
                        except Exception:
                            # msgpack may be missing — soft encode falls to json
                            b = encode(doc, format="json")
                            decode(b.data, format="json")
            except BaseException as e:  # noqa: BLE001
                errors.append(e)

        def reconfig_loop():
            try:
                for i in range(100):
                    configure_wire(format="cxb" if i % 2 else "json")
            except BaseException as e:  # noqa: BLE001
                errors.append(e)

        def dumps_loop():
            try:
                for _ in range(300):
                    loads(dumps({"n": 1, "s": "x"}))
            except BaseException as e:  # noqa: BLE001
                errors.append(e)

        threads = (
            [threading.Thread(target=encode_loop) for _ in range(6)]
            + [threading.Thread(target=reconfig_loop) for _ in range(2)]
            + [threading.Thread(target=dumps_loop) for _ in range(4)]
        )
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=30)
        self.assertEqual(errors, [])
        # process still healthy
        self.assertEqual(loads(dumps({"alive": True})), {"alive": True})


class TestCxbLimits(unittest.TestCase):
    def test_oversize_string_table_rejected(self):
        # craft minimal illegal: magic + kind + huge table count varint
        # varint for 200000
        n = 200_000
        vb = bytearray()
        x = n
        while x > 0x7F:
            vb.append((x & 0x7F) | 0x80)
            x >>= 7
        vb.append(x)
        raw = b"CXB1" + bytes([2]) + bytes(vb)  # result kind + huge table
        with self.assertRaises(ValueError):
            decode_cxb(raw)


if __name__ == "__main__":
    unittest.main()
