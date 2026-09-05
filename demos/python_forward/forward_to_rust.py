#!/usr/bin/env python3
"""Minimal Python → Rust peer forward.

Sends one hot action (Cart.add) to the Rust HTTP peer and returns Result.ops
unchanged to the caller. Mint is Channel / cek-runtime Host when available,
else local itsdangerous (classic floor). Peer is verify-only (no /mint).

Usage:
  # terminal A (demo secret — see OPERATIONAL.md)
  UXC_ALLOW_ORACLE_SECRET=1 cargo run --bin uxc_peer

  # terminal B
  python3 demos/python_forward/forward_to_rust.py
  python3 demos/python_forward/forward_to_rust.py --base http://127.0.0.1:8787
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import urllib.error
import urllib.request
from typing import Any

try:
    from itsdangerous import URLSafeTimedSerializer
except ImportError:
    URLSafeTimedSerializer = None  # type: ignore

ORACLE_SECRET = "conformance-oracle-secret-32chars!!"
SALT = "ux-channel-cap"
DEFAULT_BASE = "http://127.0.0.1:8787"


def hash_args(args: dict[str, Any]) -> str:
    raw = json.dumps(args, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]


def mint_cap_python(action: str, args: dict[str, Any], *, sub: str = "user:42") -> str:
    """Classic-floor itsdangerous mint (same tokens Rust Peer verifies)."""
    if URLSafeTimedSerializer is None:
        raise RuntimeError("itsdangerous not installed")
    import time

    ser = URLSafeTimedSerializer(secret_key=ORACLE_SECRET, salt=SALT)
    payload = {
        "action": action,
        "args_hash": hash_args(args),
        "iat": int(time.time()),
        "sub": sub,
        "scopes": ["cart:write"],
    }
    return ser.dumps(payload)


def forward_intent(base: str, intent: dict[str, Any]) -> dict[str, Any]:
    """POST Intent to Rust peer; return Result as dict (ops untouched)."""
    data = json.dumps(intent, separators=(",", ":")).encode()
    req = urllib.request.Request(
        f"{base.rstrip('/')}/ux-channel/action",
        data=data,
        headers={
            "Content-Type": "application/ux-channel+json",
            "Accept": "application/ux-channel+json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        try:
            return json.loads(body)
        except json.JSONDecodeError:
            raise RuntimeError(f"HTTP {e.code}: {body}") from e


def main() -> int:
    ap = argparse.ArgumentParser(description="Forward Cart.add to Rust ux-channel peer")
    ap.add_argument("--base", default=DEFAULT_BASE, help="Rust peer base URL")
    ap.add_argument("--sku", default="abc-123")
    ap.add_argument("--qty", type=int, default=2)
    args = ap.parse_args()

    sealed = {"sku": args.sku, "qty": args.qty}
    # Classic-floor token for the Rust Peer hop (Peer is verify-only).
    # Product mint is Channel / cek-runtime Host — see scripts/cross_mint_check.py.
    try:
        cap = mint_cap_python("Cart.add", sealed)
    except RuntimeError as e:
        print(e, file=sys.stderr)
        print("hint: pip install itsdangerous", file=sys.stderr)
        return 2

    intent = {
        "v": "1",
        "action": "Cart.add",
        "args": sealed,
        "cap": cap,
        "request_id": "py-forward-1",
    }
    result = forward_intent(args.base, intent)
    print(json.dumps(result, indent=2))
    if not result.get("ok"):
        return 1
    ops = result.get("ops") or []
    print(f"# ops returned unchanged: {len(ops)}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
