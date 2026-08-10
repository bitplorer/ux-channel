"""
Signed confirmation tokens for MCP / agent high-stakes tools.

Token binds: action + args_hash + session_id + agent_id + jti + exp.
"""

from __future__ import annotations

from ux_channel.protocol import serde as _serde

import hashlib
import json
import time
import uuid
from typing import Any, Mapping, Optional

from itsdangerous import BadSignature, URLSafeTimedSerializer

__all__ = [
    "mint_confirm_token",
    "verify_confirm_token",
    "args_hash",
    "CONFIRM_SALT",
]

CONFIRM_SALT = "ux-channel-mcp-confirm-v1"


def args_hash(arguments: Mapping[str, Any] | None) -> str:
    """Stable short hash of tool arguments for confirm-token binding."""
    raw = _serde.dumps(arguments or {}, default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]


def _ser(secret: str) -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(str(secret), salt=CONFIRM_SALT)


def mint_confirm_token(
    secret: str,
    *,
    action: str,
    arguments: Mapping[str, Any] | None,
    session_id: str,
    agent_id: str,
    ttl_s: float = 120,
) -> tuple[str, float]:
    """Return (token, expires_at_unix)."""
    if not secret or len(str(secret)) < 16:
        raise ValueError("confirm mint requires secret length >= 16")
    exp = time.time() + max(30.0, float(ttl_s))
    payload = {
        "v": 1,
        "action": action,
        "args_hash": args_hash(arguments),
        "session_id": session_id,
        "agent_id": agent_id,
        "jti": uuid.uuid4().hex,
        "exp": exp,
    }
    tok = _ser(secret).dumps(payload)
    return tok, exp


def verify_confirm_token(
    secret: str,
    token: str,
    *,
    action: str,
    arguments: Mapping[str, Any] | None,
    session_id: str,
    agent_id: str,
    max_age_s: float = 180,
    nonce_store: Any = None,
) -> tuple[bool, str]:
    """
    Verify confirmation token.

    Returns (ok, reason). If nonce_store given, burns jti (once).
    """
    if not token or not secret:
        return False, "missing"
    # Plain secret equality is not accepted — use signed confirmation tokens only.
    try:
        data = _ser(secret).loads(token, max_age=int(max_age_s))
    except BadSignature:
        return False, "bad_signature"
    except Exception as exc:
        return False, f"invalid:{exc}"
    if not isinstance(data, dict):
        return False, "payload"
    if data.get("action") != action:
        return False, "action_mismatch"
    if data.get("args_hash") != args_hash(arguments):
        return False, "args_mismatch"
    if data.get("session_id") != session_id:
        return False, "session_mismatch"
    if data.get("agent_id") != agent_id:
        return False, "agent_mismatch"
    exp = float(data.get("exp") or 0)
    if exp and time.time() > exp:
        return False, "expired"
    jti = data.get("jti")
    if nonce_store is not None and jti:
        try:
            # MemoryNonceStore-like: use once
            key = f"mcp_confirm:{jti}"
            if hasattr(nonce_store, "seen"):
                if nonce_store.seen(key):
                    return False, "replay"
                nonce_store.mark(key)
            elif hasattr(nonce_store, "check_and_use"):
                if not nonce_store.check_and_use(key):
                    return False, "replay"
            else:
                # set-like
                if jti in nonce_store:
                    return False, "replay"
                nonce_store.add(jti)
        except Exception:
            pass
    return True, "ok"
