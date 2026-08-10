"""Python host must agree with shared law (conformance/) and Cap/CXB basics.

Monorepo **sync suite**: Python + Rust both pass the same vectors. Failures here
mean IR/cap/CXB drift between languages.
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "python"))

from ux_channel.capability import CapabilityError, CapabilityService  # noqa: E402
from ux_channel.wire import decode, encode  # noqa: E402
from ux_channel.wire.cxb import decode_cxb, encode_cxb, is_cxb  # noqa: E402

CONF = ROOT / "conformance"
ORACLE_SECRET = "conformance-oracle-secret-32chars!!"


def _load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def test_python_package_imports():
    from ux_channel.wire.cxb import MEDIA_TYPE

    assert MEDIA_TYPE == "application/ux-channel+cxb"


@pytest.mark.parametrize(
    "rel",
    [
        "vectors/intent/01-minimal.json",
        "vectors/intent/02-with-request-id.json",
        "vectors/intent/04-unknown-fields-ignored.json",
        "vectors/result/01-ok-morph.json",
        "vectors/result/02-ok-toast.json",
        "vectors/result/03-error-unauthorized.json",
        "vectors/result/04-error-validation.json",
        "vectors/result/07-ok-multi-ops.json",
    ],
)
def test_json_vector_roundtrip_via_wire(rel: str):
    doc = _load_json(CONF / rel)
    blob = encode(doc)
    again = decode(blob.data)
    assert json.loads(json.dumps(again, sort_keys=True)) == json.loads(
        json.dumps(doc, sort_keys=True)
    )


def test_args_hash_matches_rust_and_oracle_algorithm():
    args = {"sku": "abc-123", "qty": 2}
    raw = json.dumps(args, sort_keys=True, separators=(",", ":"), default=str)
    expected = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]
    assert expected == "96e4f83e3793b646323a67f314b51044"
    svc = CapabilityService(ORACLE_SECRET)
    assert svc._hash_args(args) == expected


def test_cap_oracle_token_verifies():
    vec = _load_json(CONF / "vectors/cap/02-oracle-token.json")
    svc = CapabilityService(vec["oracle"]["secret"], max_age=86400 * 365 * 20)
    out = svc.verify(
        vec["token"],
        action=vec["payload"]["action"],
        args=vec["sealed_args"],
        max_age=86400 * 365 * 20,
    )
    assert out["action"] == "Cart.add"
    assert out["args_hash"] == vec["payload"]["args_hash"]


def test_cap_sign_verify_roundtrip():
    svc = CapabilityService(ORACLE_SECRET, max_age=3600)
    args = {"sku": "abc-123", "qty": 2}
    token = svc.sign("Cart.add", args, sub="user:42", scopes=["cart:write"])
    payload = svc.verify(token, action="Cart.add", args=args)
    assert payload["action"] == "Cart.add"
    with pytest.raises(CapabilityError):
        svc.verify(token, action="Cart.add", args={"sku": "abc-123", "qty": 999})


def test_cxb_expected_blobs_decode_and_reencode():
    index = _load_json(CONF / "expected/cxb/index.json")
    vectors = index["vectors"]
    checked = 0
    for ent in vectors:
        file = ent["file"] if isinstance(ent, dict) else ent
        path = CONF / file
        if not path.exists():
            path = CONF / "expected/cxb" / Path(file).name
        if not path.exists():
            continue
        blob = path.read_bytes()
        assert is_cxb(blob), file
        doc = decode_cxb(blob)
        assert isinstance(doc, dict)
        re = encode_cxb(doc)
        re_bytes = re if isinstance(re, (bytes, bytearray)) else bytes(re)
        assert is_cxb(re_bytes)
        checked += 1
    assert checked >= 10, checked


def test_manifest_ir_version():
    m = _load_json(CONF / "manifest.json")
    assert str(m.get("ir_version")) == "1"
