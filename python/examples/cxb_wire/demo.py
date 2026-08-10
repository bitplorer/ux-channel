#!/usr/bin/env python3
"""CXB usage — encode/decode Results and optional HTTP Accept negotiation."""

from __future__ import annotations

from ux_channel.wire import (
    configure_wire,
    decode,
    encode,
    encode_http_body,
    reset_wire,
)
from ux_channel.wire.cxb import decode_cxb, encode_cxb, is_cxb


def main() -> None:
    result = {
        "v": "1",
        "ok": True,
        "ops": [
            {"op": "toast", "message": "Saved", "level": "success"},
            {
                "op": "morph",
                "target": '[data-channel-id="cart"]',
                "html": "<div data-channel-id=\"cart\"><b>3</b></div>",
                "morph": "idiomorph",
            },
            # Future / plugin ops — free string + open keys
            {
                "op": "plugin.analytics.track",
                "event": "checkout",
                "payload": {"sku": "a", "n": 3},
            },
        ],
        "meta": {"action": "Cart.add", "request_id": "r1"},
    }

    # 1) Explicit low-level CXB
    raw = encode_cxb(result)
    assert is_cxb(raw)
    back = decode_cxb(raw)
    assert back["ops"][0]["message"] == "Saved"
    assert back["ops"][2]["op"] == "plugin.analytics.track"
    print(f"encode_cxb: {len(raw)} bytes  magic={raw[:4]!r}")

    # 2) Process policy (all encode() calls use CXB until reset)
    configure_wire(format="cxb")
    blob = encode(result)
    print(f"encode():   {len(blob.data)} bytes  format={blob.format}  media={blob.media_type}")
    doc = decode(blob.data)  # sniffs CXB1 / complete chain
    assert doc["ok"] is True

    # 3) Per-call format (no process policy change)
    reset_wire()  # back to JSON default
    blob_json = encode(result, format="json")
    blob_cxb = encode(result, format="cxb")
    print(f"json vs cxb size: {len(blob_json.data)} → {len(blob_cxb.data)} bytes")

    # 4) HTTP-style response for a client that Accepts CXB
    http_blob = encode_http_body(
        result,
        accept="application/ux-channel+cxb, application/json",
    )
    print(f"HTTP body:  format={http_blob.format}  Content-Type={http_blob.media_type}")

    reset_wire()
    print("ok")


if __name__ == "__main__":
    main()
