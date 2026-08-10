"""
Normalize Result → agent-facing effects envelope (MCP _meta.effects).

Pure functions — no I/O. Additive; does not replace structuredContent Result.
"""

from __future__ import annotations

import re
from typing import Any, Mapping, Optional

from ux_channel.protocol.types import Result

__all__ = ["effects_from_result", "region_uid_from_target"]

_UID_IN_TARGET = re.compile(r'data-channel-id=["\']([^"\']+)["\']')
_UID_BARE = re.compile(r"^#?([A-Za-z0-9_.:-]+)$")


def region_uid_from_target(target: Any) -> Optional[str]:
    """Extract region uid from morph/swap target selector if present."""
    if not target:
        return None
    s = str(target).strip()
    m = _UID_IN_TARGET.search(s)
    if m:
        return m.group(1)
    # [data-channel-id=cart] without quotes
    m2 = re.search(r"data-channel-id=([A-Za-z0-9_.:-]+)", s)
    if m2:
        return m2.group(1)
    return None


def effects_from_result(result: Result) -> dict[str, Any]:
    """
    Compact effects view for MCP hosts.

    Never includes caps, tickets, or secrets.
    """
    ops_out: list[dict[str, Any]] = []
    regions: list[str] = []
    toasts: list[dict[str, Any]] = []
    navigated: Optional[str] = None
    signals: dict[str, Any] = {}
    bridges: list[str] = []
    refresh: list[str] = []

    for op in list(result.ops or []):
        if not isinstance(op, Mapping):
            continue
        kind = op.get("op") or op.get("type")
        entry: dict[str, Any] = {"op": kind}
        if kind in ("morph", "swap"):
            target = op.get("target")
            entry["target"] = target
            uid = region_uid_from_target(target)
            if uid:
                entry["uid"] = uid
                if uid not in regions:
                    regions.append(uid)
        elif kind == "toast":
            msg = op.get("message") or op.get("text") or ""
            level = op.get("level") or "info"
            entry["message"] = msg
            entry["level"] = level
            toasts.append({"level": level, "message": msg})
        elif kind == "navigate":
            href = op.get("href") or op.get("url")
            entry["href"] = href
            navigated = href
        elif kind == "signal_set":
            path = op.get("path") or op.get("key")
            if path is not None:
                signals[str(path)] = op.get("value")
                entry["path"] = path
        elif kind and str(kind).startswith("bridge"):
            bid = op.get("id") or op.get("bridge_id")
            if bid:
                bridges.append(str(bid))
                entry["id"] = bid
        ops_out.append(entry)

    meta = dict(result.meta or {})
    # region refresh list from product meta
    for key in ("refresh", "refresh_uids", "regions"):
        val = meta.get(key)
        if isinstance(val, (list, tuple)):
            for u in val:
                s = str(u)
                if s not in refresh:
                    refresh.append(s)
                if s not in regions:
                    regions.append(s)

    err = None
    if result.error:
        err = {
            "code": result.error.code,
            "message": result.error.message,
            "retryable": bool(getattr(result.error, "retryable", False)),
        }

    needs_conf = False
    if result.error and result.error.code == "confirmation_required":
        needs_conf = True
    if meta.get("confirmation_required"):
        needs_conf = True

    out: dict[str, Any] = {
        "ok": bool(result.ok),
        "error": err,
        "ops": ops_out,
        "regions": regions,
        "toasts": toasts,
        "navigated": navigated,
        "signals": signals,
        "bridges": bridges,
        "refresh": refresh,
        "dry_run": bool(meta.get("dry_run")),
        "needs_confirmation": needs_conf,
    }
    # pass through confirm token if runner minted one (not a secret long-term)
    if meta.get("confirm_token"):
        out["confirm_token"] = meta["confirm_token"]
    if meta.get("confirm_expires_at"):
        out["confirm_expires_at"] = meta["confirm_expires_at"]
    if meta.get("would_call"):
        out["would_call"] = meta["would_call"]
    return out
