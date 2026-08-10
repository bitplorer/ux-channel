"""Capability + wire smoke for day-1 host (complements interop suite)."""
from __future__ import annotations

from ux_channel.protocol.capability import CapError, CapService
from ux_channel.day1 import CapService as Day1Cap
from ux_channel.wire import decode, encode


def test_day1_cap_is_same_class():
    assert Day1Cap is CapService


def test_sign_verify_and_reject_tampered_args(secret):
    svc = CapService(secret)
    args = {"sku": "a", "qty": 1}
    token = svc.mint("Cart.add", args, sub="u1")
    assert svc.verify(token, action="Cart.add", args=args)["action"] == "Cart.add"
    try:
        svc.verify(token, action="Cart.add", args={"sku": "a", "qty": 2})
        raise AssertionError("expected CapError")
    except CapError:
        pass


def test_wire_json_roundtrip_intent():
    doc = {"v": "1", "action": "Counter.inc", "args": {}}
    blob = encode(doc)
    assert blob.format == "json"
    assert decode(blob.data)["action"] == "Counter.inc"
