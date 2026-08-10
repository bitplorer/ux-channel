#!/usr/bin/env python3
"""Minimal Python → Rust peer forward.

Sends one hot action (Cart.add) to the Rust HTTP peer and returns Result.ops
unchanged to the caller. No dependency on the full ux-channel package.

Usage:
  # terminal A (demo secret — see OPERATIONAL.md)
  UXC_ALLOW_ORACLE_SECRET=1 cargo run --bin uxc_peer

  # terminal B
  python3 peers/python_forward/forward_to_rust.py
  python3 peers/python_forward/forward_to_rust.py --base http://127.0.0.1:8787
  python3 peers/python_forward/forward_to_rust.py --mint-via-peer
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
    """Mint with itsdangerous when available; otherwise ask Rust /ux-channel/mint."""
    if URLSafeTimedSerializer is None:
        raise RuntimeError("itsdangerous not installed; use --mint-via-peer")
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


def mint_via_peer(base: str, action: str, args: dict[str, Any]) -> str:
    body = json.dumps(
        {"action": action, "args": args, "sub": "user:42", "scopes": ["cart:write"]}
    ).encode()
    req = urllib.request.Request(
        f"{base.rstrip('/')}/ux-channel/mint",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=5) as resp:
        doc = json.loads(resp.read().decode())
    if not doc.get("ok"):
        raise RuntimeError(f"mint failed: {doc}")
    return doc["cap"]


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
        # Peer returns Result-shaped bodies even on 4xx.
        body = e.read().decode()
        try:
            return json.loads(body)
        except json.JSONDecodeError:
            raise RuntimeError(f"HTTP {e.code}: {body}") from e


def main() -> int:
    ap = argparse.ArgumentParser(description="Forward Cart.add to Rust ux-channel peer")
    ap.add_argument("--base", default=DEFAULT_BASE, help="Rust peer base URL")
    ap.add_argument(
        "--mint-via-peer",
        action="store_true",
        help="mint via POST /ux-channel/mint instead of local itsdangerous",
    )
    ap.add_argument("--sku", default="abc-123")
    ap.add_argument("--qty", type=int, default=2)
    args = ap.parse_args()

    sealed = {"sku": args.sku, "qty": args.qty}
    if args.mint_via_peer:
        cap = mint_via_peer(args.base, "Cart.add", sealed)
    else:
        try:
            cap = mint_cap_python("Cart.add", sealed)
        except RuntimeError as e:
            print(e, file=sys.stderr)
            print("hint: pip install itsdangerous  or pass --mint-via-peer", file=sys.stderr)
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
