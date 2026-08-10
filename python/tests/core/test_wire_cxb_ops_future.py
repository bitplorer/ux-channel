"""CXB must round-trip every current op builder and arbitrary future ops."""

from __future__ import annotations

import unittest

from ux_channel.protocol import ops as O
from ux_channel.wire import decode, encode, reset_wire
from ux_channel.wire.cxb import decode_cxb, encode_cxb


def _all_library_ops():
    return [
        O.morph("#a", "<b>1</b>", morph="idiomorph", meta={"k": 1}),
        O.swap("#a", "<i>2</i>", swap="innerHTML", settle_ms=40),
        O.remove("#x"),
        O.set_attr("#x", {"disabled": True, "aria-label": "go", "data-n": 3}),
        O.set_text("#x", "hello"),
        O.clear_errors("#form"),
        O.bridge_mount("m1", "chart", props={"series": [1, 2, 3]}, target="#slot"),
        O.bridge_update("m1", {"series": [4]}, replace=True),
        O.bridge_call("m1", "refresh", args=["a", {"b": True}], package="chart"),
        O.bridge_destroy("m1"),
        O.navigate("/next", replace=True),
        O.reload(),
        O.push_url("/q?x=1"),
        O.focus("#in", select=True),
        O.scroll(target="#main", top=10.5, left=0, behavior="smooth"),
        O.toast("Saved", level="success", duration_ms=1200),
        O.dispatch("cart:changed", target="#app", detail={"n": 2}, bubbles=True),
        O.signal_set("cart.count", 9),
        O.noop(meta={"dropped": "navigate", "reason": "unsafe_href"}),
    ]


class TestAllLibraryOps(unittest.TestCase):
    def test_every_builder_roundtrips_cxb(self):
        ops = _all_library_ops()
        doc = {"v": "1", "ok": True, "ops": ops, "meta": {"action": "All.run"}}
        out = decode_cxb(encode_cxb(doc))
        self.assertEqual(len(out["ops"]), len(ops))
        for i, (a, b) in enumerate(zip(ops, out["ops"])):
            self.assertEqual(a, b, msg=f"op[{i}] {a.get('op')}")


class TestFutureOps(unittest.TestCase):
    def tearDown(self):
        reset_wire()

    def test_unknown_op_type_and_keys(self):
        op = {
            "op": "plugin.billing.refund",
            "invoice_id": "inv_9",
            "amount": {"currency": "INR", "minor": 49900},
            "nested": [{"x": True}, None, 1.25],
            "meta": {"trace": "t1", "flags": ["a", "b"]},
            "custom_flag": False,
        }
        doc = {"v": "1", "ok": True, "ops": [op]}
        out = decode_cxb(encode_cxb(doc))
        self.assertEqual(out["ops"][0], op)

    def test_unicode_op_and_html(self):
        op = {
            "op": "通知.显示",
            "message": "订单完成 🎉",
            "html": "<div>café</div>",
            "target": '[data-channel-id="订单"]',
        }
        out = decode_cxb(encode_cxb({"v": "1", "ok": True, "ops": [op]}))
        self.assertEqual(out["ops"][0], op)

    def test_deeply_nested_payload(self):
        tree = {"a": 1}
        cur = tree
        for i in range(20):
            cur["c"] = {"i": i, "L": [i, {"j": i}]}
            cur = cur["c"]
        op = {"op": "tree.apply", "payload": tree, "config": {"mode": "deep"}}
        out = decode_cxb(encode_cxb({"v": "1", "ok": True, "ops": [op]}))
        self.assertEqual(out["ops"][0]["payload"], tree)

    def test_many_free_keys_op(self):
        op = {"op": "wide"}
        for i in range(80):
            op[f"field_{i}"] = i
        out = decode_cxb(encode_cxb({"v": "1", "ok": True, "ops": [op]}))
        self.assertEqual(out["ops"][0], op)

    def test_mixed_result_via_wire_encode(self):
        ops = _all_library_ops() + [
            {"op": "future.x", "payload": {"ok": True}, "meta": {"v": 2}}
        ]
        blob = encode({"v": "1", "ok": True, "ops": ops}, format="cxb")
        back = decode(blob.data, format="cxb")
        self.assertEqual(len(back["ops"]), len(ops))
        self.assertEqual(back["ops"][-1]["op"], "future.x")
        self.assertEqual(back["ops"][0]["op"], "morph")

    def test_preserve_false_and_zero(self):
        op = {
            "op": "flags",
            "replace": False,  # may be omitted by builders; custom keeps it
            "bubbles": False,
            "value": 0,
            "count": 0,
        }
        out = decode_cxb(encode_cxb({"v": "1", "ok": True, "ops": [op]}))
        self.assertIs(out["ops"][0]["replace"], False)
        self.assertIs(out["ops"][0]["bubbles"], False)
        self.assertEqual(out["ops"][0]["value"], 0)


if __name__ == "__main__":
    unittest.main()
