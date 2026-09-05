#!/usr/bin/env python3
"""Prove Channel/cek-runtime Host mints; Rust Peer only verifies.

Requires live peer (demo oracle). Exit 0 on success.
  UXC peer must use the same oracle secret (startup-peer.sh).
  Peer has no POST /ux-channel/mint (ADR 0011).
"""
from __future__ import annotations

import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "python" / "src"))

from ux_channel.protocol.capability import CapService  # noqa: E402

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


def _channel_host_mint(action: str, args: dict) -> str:
    """Mint on the product Cap machine (cek-runtime Host)."""
    from ux_channel.host.factory import create_channel

    reg, _hub = create_channel(
        secret=ORACLE,
        environment="development",
        app=None,
        host=None,
    )
    caps = reg._caps
    if type(caps).__name__ != "CekHostCapService":
        raise SystemExit(f"cross_mint: Cap machine is {type(caps).__name__}, want CekHostCapService")
    if getattr(caps, "kernel_ssot", None) != "cek-runtime":
        raise SystemExit("cross_mint: kernel_ssot is not cek-runtime")
    token = reg.mint(action, args)
    caps.verify(token, action, args)
    return token


def main() -> int:
    st, _ = http_json("GET", "/ux-channel/health")
    if st != 200:
        print("cross_mint: peer not healthy", st, file=sys.stderr)
        return 1

    st_mint, mint_body = http_json(
        "POST",
        "/ux-channel/mint",
        {"action": "Cart.add", "args": {"sku": "must-404", "qty": 1}},
    )
    if st_mint not in (404, 405):
        print("cross_mint: peer mint must be gone", st_mint, mint_body, file=sys.stderr)
        return 1

    try:
        _channel_host_mint("Cart.add", {"sku": "cross-host", "qty": 1})
    except SystemExit:
        raise
    except Exception as exc:
        print("cross_mint: Channel/cek-runtime Host mint failed:", exc, file=sys.stderr)
        return 1

    # Classic floor tokens still verify on the Rust peer (shared itsdangerous).
    # Peer does not mint.
    svc = CapService(ORACLE, max_age=3600)
    args = {"sku": "cross-py", "qty": 2}
    token = svc.mint("Cart.add", args, sub="user:cross", scopes=["cart:write"])
    st, result = http_json(
        "POST",
        "/ux-channel/action",
        {"v": "1", "action": "Cart.add", "args": args, "cap": token},
    )
    if st != 200 or not result.get("ok"):
        print("cross_mint: Rust rejected classic-floor cap", st, result, file=sys.stderr)
        return 1

    print("cross_mint: Channel Host mint + Rust Peer verify-only OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
