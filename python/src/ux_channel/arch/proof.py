"""
Host-directed effect proofs — HMAC over Result body hash.
Key MUST differ from Cap secret.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import time
from typing import Any, Mapping, Optional


class ProofError(Exception):
    pass


class ProofService:
    def __init__(self, secret: bytes | str, *, kid: str = "p1", max_age_s: float = 120) -> None:
        self.secret = secret if isinstance(secret, bytes) else secret.encode("utf-8")
        if len(self.secret) < 16:
            raise ProofError("proof secret too short")
        self.kid = kid
        self.max_age_s = float(max_age_s)

    @staticmethod
    def body_hash(result: Mapping[str, Any]) -> str:
        core = {
            "ok": result.get("ok"),
            "ops": result.get("ops") or [],
            "error": result.get("error"),
        }
        raw = json.dumps(core, sort_keys=True, separators=(",", ":"), default=str)
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def sign(
        self,
        result: dict,
        *,
        session_id: str,
        gen: int,
        jti: Optional[str] = None,
    ) -> dict:
        bh = self.body_hash(result)
        jti = jti or secrets.token_urlsafe(12)
        # Integer unix seconds — stable across Python / JS / Rust JSON.
        exp = int(time.time()) + int(self.max_age_s)
        payload = {
            "session_id": session_id,
            "gen": int(gen),
            "jti": jti,
            "exp": exp,
            "body_hash": bh,
            "kid": self.kid,
        }
        raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        sig = hmac.new(self.secret, raw, hashlib.sha256).digest()
        payload["sig"] = base64.urlsafe_b64encode(sig).decode("ascii").rstrip("=")
        meta = dict(result.get("meta") or {})
        meta["effect"] = payload
        result["meta"] = meta
        return result

    def verify(self, result: Mapping[str, Any], *, session_id: str, gen: int) -> bool:
        meta = result.get("meta") or {}
        if not isinstance(meta, dict):
            return False
        eff = meta.get("effect")
        if not isinstance(eff, dict):
            return False
        try:
            if str(eff.get("session_id")) != str(session_id):
                return False
            if int(eff.get("gen")) != int(gen):
                return False
            if int(time.time()) > int(eff["exp"]):
                return False
            if eff.get("body_hash") != self.body_hash(result):
                return False
            payload = {
                "session_id": eff["session_id"],
                "gen": int(eff["gen"]),
                "jti": eff["jti"],
                "exp": int(eff["exp"]),
                "body_hash": eff["body_hash"],
                "kid": eff["kid"],
            }
            raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
            expect = hmac.new(self.secret, raw, hashlib.sha256).digest()
            sig_b64 = str(eff.get("sig") or "")
            pad = sig_b64 + "=" * (-len(sig_b64) % 4)
            sig = base64.urlsafe_b64decode(pad)
            return hmac.compare_digest(expect, sig)
        except (TypeError, ValueError, KeyError, json.JSONDecodeError):
            return False
