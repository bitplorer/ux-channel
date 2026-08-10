#!/usr/bin/env python3
"""Minimal Python → Rust peer forward.

Sends one hot action (Cart.add) to the Rust HTTP peer and returns Result.ops
unchanged to the caller. No dependency on the full ux-channel package.

Usage:
  # terminal A
  cargo run --bin uxc_peer

  # terminal B
  python3 peers/python_forward/forward_to_rust.py
  python3 peers/python_forward/forward_to_rust.py --base http://127.0.0.1:8787
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
            "Accept": "application/ux-channel+json, application/json",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=5) as resp:
        return json.loads(resp.read().decode())


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Forward one Cart.add Intent to the Rust peer")
    p.add_argument("--base", default=DEFAULT_BASE, help="Rust peer base URL")
    p.add_argument(
        "--mint-via-peer",
        action="store_true",
        help="Mint cap via Rust /ux-channel/mint instead of Python itsdangerous",
    )
    p.add_argument("--sku", default="abc-123")
    p.add_argument("--qty", type=int, default=2)
    args = p.parse_args(argv)

    sealed = {"sku": args.sku, "qty": args.qty}
    action = "Cart.add"

    try:
        if args.mint_via_peer or URLSafeTimedSerializer is None:
            cap = mint_via_peer(args.base, action, sealed)
            mint_src = "rust-peer"
        else:
            cap = mint_cap_python(action, sealed)
            mint_src = "python-itsdangerous"
    except Exception as e:
        print(f"mint failed: {e}", file=sys.stderr)
        return 2

    intent = {
        "v": "1",
        "action": action,
        "args": sealed,
        "cap": cap,
        "request_id": "py-forward-1",
    }

    try:
        result = forward_intent(args.base, intent)
    except urllib.error.URLError as e:
        print(f"forward failed (is uxc_peer running?): {e}", file=sys.stderr)
        return 3

    # Contract: ops returned unchanged to the client
    ops = result.get("ops", [])
    print(
        json.dumps(
            {
                "forward": "python→rust",
                "mint": mint_src,
                "intent_action": action,
                "result_ok": result.get("ok"),
                "ops": ops,
                "error": result.get("error"),
                "meta": result.get("meta"),
            },
            indent=2,
        )
    )
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
