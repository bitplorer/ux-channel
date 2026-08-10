"""
Teachable failures — map error codes / results to recipes and fixes.

Long-term: every failure should answer *what to do next*, not only *what broke*.
"""

from __future__ import annotations

from typing import Any, Mapping, Optional

__all__ = ["explain", "explain_code", "TEACH", "HINTS_BY_CODE"]

# code → short teach line (also used as Result.message suffix or details)
TEACH: dict[str, str] = {
    "unauthorized": (
        "Sign the control: place ch.control(action, trust_…).as_dict() on the "
        "button/form (recipe: ux-dom-control | form). Caps travel as data-channel-cap."
    ),
    "missing_capability": (
        "Intent had no cap. Use ch.control(action) so the client sends data-channel-cap. "
        "See: Channel.help('ux-dom-control')"
    ),
    "capability_expired": (
        "Cap TTL elapsed — re-render the control (SSR/morph) to mint a fresh cap."
    ),
    "invalid_capability": (
        "Cap signature failed — wrong secret, tampered args, or stale HTML. "
        "Do not hand-build data-channel-cap; use ch.control(...)."
    ),
    "validation": (
        "Fix field errors (error.fields) and re-submit. Recipe: form"
    ),
    "not_found": (
        "Action name not registered — @ch.on def name or registry.action. "
        "Check ch.diagnose()['actions']."
    ),
    "rate_limited": (
        "Slow down or raise bulkhead/rate limits. Retryable; honor Retry-After."
    ),
    "forbidden": (
        "Principal/roles/scopes failed — check @ch.on(roles=…) / enterprise policy."
    ),
    "conflict": (
        "State version conflict — reload region and retry (optimistic concurrency)."
    ),
    "unavailable": (
        "Dependency down (Redis/store). Check REDIS_URL and multi-worker stores."
    ),
    "sfu_not_configured": (
        "Set LIVEKIT_URL + LIVEKIT_API_KEY + LIVEKIT_API_SECRET "
        "(sfu_provider='livekit') or use mode='mesh'. Recipe: media-sfu | media-mesh"
    ),
    "rtc_ticket": (
        "Mint ch.webrtc.sign_ticket(room, sub=user) / media plugin ticket; "
        "enable webrtc_require_ticket in production."
    ),
    "origin": (
        "Set ChannelConfig allowed_origins / same-origin; send Origin header."
    ),
}

HINTS_BY_CODE = TEACH  # alias


def explain_code(code: str, *, message: str = "") -> dict[str, Any]:
    """Structured explanation for a stable error code."""
    c = (code or "").strip().lower().replace(" ", "_")
    # normalize aliases
    aliases = {
        "missing capability": "missing_capability",
        "cap_missing": "missing_capability",
        "authentication required": "unauthorized",
        "invalid capability": "invalid_capability",
        "capability expired": "capability_expired",
    }
    c = aliases.get(c, c)
    if c not in TEACH and message:
        ml = message.lower()
        if "missing capability" in ml:
            c = "missing_capability"
        elif "capability expired" in ml:
            c = "capability_expired"
        elif "invalid capability" in ml:
            c = "invalid_capability"
        elif "sfu" in ml and "config" in ml:
            c = "sfu_not_configured"
        elif "ticket" in ml:
            c = "rtc_ticket"
        elif "origin" in ml:
            c = "origin"
    teach = TEACH.get(c) or TEACH.get("unauthorized") if c == "unauthorized" else TEACH.get(c)
    if teach is None:
        teach = (
            f"See Channel.help() and error_map for code={code!r}. "
            "uxchannel recipe --tree"
        )
    recipe = _recipe_for(c)
    return {
        "code": c or code,
        "message": message,
        "teach": teach,
        "recipe": recipe,
        "help": f"Channel.help({recipe!r})" if recipe else "Channel.help()",
        "cli": f"uxchannel recipe {recipe}" if recipe else "uxchannel recipe --tree",
    }


def _recipe_for(code: str) -> str | None:
    return {
        "unauthorized": "ux-dom-control",
        "missing_capability": "ux-dom-control",
        "capability_expired": "ux-dom-control",
        "invalid_capability": "ux-dom-control",
        "validation": "form",
        "sfu_not_configured": "media-sfu",
        "rtc_ticket": "media-mesh",
        "not_found": "counter",
    }.get(code)


def explain(result_or_code: Any, message: str = "") -> dict[str, Any]:
    """
    Explain a Result, error dict, or code string.

    ::

        r = reg.dispatch(intent)
        print(ch.explain(r))
    """
    if isinstance(result_or_code, str):
        return explain_code(result_or_code, message=message)
    # Result-like
    err = None
    if hasattr(result_or_code, "error"):
        err = getattr(result_or_code, "error")
    elif isinstance(result_or_code, Mapping):
        err = result_or_code.get("error")
        if err is None and "code" in result_or_code:
            return explain_code(
                str(result_or_code.get("code")),
                message=str(result_or_code.get("message") or message),
            )
    if err is None:
        return {
            "code": None,
            "message": message or "ok",
            "teach": "No error on result — action succeeded.",
            "recipe": None,
            "help": "Channel.help()",
            "cli": "uxchannel doctor",
            "ok": True,
        }
    if hasattr(err, "code"):
        code = str(err.code)
        msg = str(getattr(err, "message", "") or message)
    elif isinstance(err, Mapping):
        code = str(err.get("code") or "")
        msg = str(err.get("message") or message)
    else:
        code = "unknown"
        msg = str(err)
    out = explain_code(code, message=msg)
    out["ok"] = False
    return out
