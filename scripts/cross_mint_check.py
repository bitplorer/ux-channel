#!/usr/bin/env python3
"""Prove Python CapService and Rust uxc_peer share cap crypto.

Requires live peer (demo oracle). Exit 0 on success.
  UXC peer must use the same oracle secret (startup-peer.sh).
"""
from __future__ import annotations

import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "python"))

from ux_channel.capability import CapService  # noqa: E402

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8787"
ORACLE = "conformance-oracle-secret-32chars!!"


def http_json(method: str, path: str, body=None):
    data = None if body is None else json.dumps(body).encode()
    req = urllib.request.Request(
        BASE + path,
        data=data,
        method=method,
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=5) as r:
            return r.status, json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        raw = e.read().decode()
        try:
            return e.code, json.loads(raw)
        except Exception:
            return e.code, {"raw": raw}


def main() -> int:
    svc = CapService(ORACLE, max_age=3600)
    st, _ = http_json("GET", "/ux-channel/health")
    if st != 200:
        print("cross_mint: peer not healthy", st, file=sys.stderr)
        return 1

    # Python → Rust
    args = {"sku": "cross-py", "qty": 2}
    token = svc.mint("Cart.add", args, sub="user:cross", scopes=["cart:write"])
    st, result = http_json(
        "POST",
        "/ux-channel/action",
        {"v": "1", "action": "Cart.add", "args": args, "cap": token},
    )
    if st != 200 or not result.get("ok"):
        print("cross_mint: Rust rejected Python cap", st, result, file=sys.stderr)
        return 1

    # Rust → Python
    st, mint = http_json(
        "POST",
        "/ux-channel/mint",
        {
            "action": "Cart.add",
            "args": {"sku": "cross-rs", "qty": 3},
            "sub": "user:rs",
            "scopes": ["cart:write"],
        },
    )
    token2 = (mint or {}).get("cap") or (mint or {}).get("token")
    if st != 200 or not token2:
        print("cross_mint: mint failed", st, mint, file=sys.stderr)
        return 1
    out = svc.verify(token2, action="Cart.add", args={"sku": "cross-rs", "qty": 3})
    if out.get("action") != "Cart.add":
        print("cross_mint: Python rejected Rust cap", out, file=sys.stderr)
        return 1

    print("cross_mint: Python↔Rust cap interop OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
