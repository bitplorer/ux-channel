"""Error plane — codes → HTTP status, client kind, batch envelope status.

A Result body is the source of truth (``ok`` / ``error.code``). HTTP status
is a cache/proxy convenience. This module is the **only** mapping table so
FastAPI, Starlette, and batch envelopes never diverge.

Also:

- ``ensure_error_meta`` fills ``error_kind`` / ``retryable`` defaults
- ``batch_http_status`` /…"""
from __future__ import annotations

from typing import Any, Mapping, Optional

from ux_channel.protocol.types import Result

# Canonical codes → HTTP status
# Keep keys lowercase snake_case. Unknown codes → DEFAULT_ERROR_STATUS.
ERROR_HTTP_STATUS: dict[str, int] = {
    # Auth / access
    "unauthorized": 401,
    "forbidden": 403,
    "confirmation_required": 403,
    # Client request shape
    "bad_request": 400,
    "validation": 422,
    "not_found": 404,
    "payload_too_large": 413,
    "upgrade_required": 426,
    "conflict": 409,
    # Throttle / time
    "rate_limited": 429,
    "timeout": 504,
    # Server
    "internal": 500,
    "encode_error": 500,
    "render_error": 500,  # region paint/load failed (not a bad Intent)
    # Rare / agent
    "not_implemented": 501,
    "unavailable": 503,
}

DEFAULT_ERROR_STATUS = 422  # unprocessable — safe default for app-level failures

# Codes that should advertise retryable=True when not set by caller
RETRYABLE_CODES: frozenset[str] = frozenset(
    {
        "rate_limited",
        "timeout",
        "unavailable",
        "render_error",  # transient paint/load often retryable
        # note: "internal" is intentionally NOT auto-retryable (thundering herd)
    }
)

# Client error plane kinds (channel:error.kind)
CODE_TO_KIND: dict[str, str] = {
    "unauthorized": "auth",
    "forbidden": "auth",
    "confirmation_required": "auth",
    "validation": "validation",
    "bad_request": "protocol",
    "not_found": "protocol",
    "payload_too_large": "protocol",
    "upgrade_required": "protocol",
    "conflict": "protocol",
    "rate_limited": "network",
    "timeout": "network",
    "unavailable": "network",
    "render_error": "refresh",
    "internal": "protocol",
    "encode_error": "protocol",
    "not_implemented": "protocol",
    "network": "network",  # client synthetic
}


def http_status_for(
    result: Result | Mapping[str, Any],
    *,
    default_ok: int = 200,
    default_err: int = DEFAULT_ERROR_STATUS,
) -> int:
    """
    Map a Result to an HTTP status code.

    Success → 200 (even if ops are empty).
    Failure → ERROR_HTTP_STATUS[code] or default_err (422).
    """
    if isinstance(result, Result):
        if result.ok:
            return default_ok
        code = (result.error.code if result.error else "") or ""
    else:
        if result.get("ok", True):
            return default_ok
        err = result.get("error") or {}
        if isinstance(err, Mapping):
            code = str(err.get("code") or "")
        else:
            code = str(getattr(err, "code", "") or "")
    return ERROR_HTTP_STATUS.get(code, default_err)


def kind_for_code(code: str | None) -> str:
    """Client-plane kind for an error code."""
    if not code:
        return "unknown"
    return CODE_TO_KIND.get(str(code), "protocol")


def should_retry(code: str | None, *, explicit: Optional[bool] = None) -> bool:
    if explicit is not None:
        return bool(explicit)
    if not code:
        return False
    # internal is NOT auto-retryable (avoid thundering herd)
    if code == "internal":
        return False
    return code in RETRYABLE_CODES


def ensure_error_meta(result: Result) -> Result:
    """
    Normalize failure Results: fill retryable + client kind in meta when missing.

    Safe to call from _finalize / host adapters. Does not change ok Results.
    """
    if result.ok or not result.error:
        return result
    code = result.error.code
    # Fill retryable on ErrorObject if unset
    if result.error.retryable is None and should_retry(code):
        result.error.retryable = True
    meta = dict(result.meta or {})
    meta.setdefault("error_kind", kind_for_code(code))
    meta.setdefault("http_status", http_status_for(result))
    # Note: do NOT invent meta.retry_after here — only producers (rate_limit_hook,
    # app code) should set it. HTTP adapters default Retry-After header for 429
    # without mutating the body, so batch backoff is not forced to 5s.
    result.meta = meta
    return result


def catalog() -> list[dict[str, Any]]:
    """Documentable list of codes (for /ux-channel/catalog or docs)."""
    rows = []
    for code, status in sorted(ERROR_HTTP_STATUS.items()):
        rows.append(
            {
                "code": code,
                "http_status": status,
                "kind": kind_for_code(code),
                "retryable_default": should_retry(code),
            }
        )
    return rows


# Batch envelope status
# A batch response is NOT a single Result when items ran:
#   { "ok": bool, "batch": [Result, ...], "ops": [...], "meta": {...} }
# Oversized/invalid batch may still be a single Result.failure dict.
#
# HTTP for the envelope:
#   all items ok     → 200
#   mixed ok/fail    → 207 Multi-Status
#   all items fail   → worst item status (see severity)
#   envelope error   → http_status_for(that Result)  e.g. 413

_BATCH_STATUS_SEVERITY: tuple[int, ...] = (
    500,
    504,
    503,
    501,
    429,
    401,
    403,
    413,
    409,
    404,
    400,
    426,
    422,
)


def _severity_rank(status: int) -> int:
    try:
        return _BATCH_STATUS_SEVERITY.index(status)
    except ValueError:
        # unknown → treat near 422
        return len(_BATCH_STATUS_SEVERITY)


def batch_http_status(envelope: Mapping[str, Any]) -> int:
    """
    HTTP status for a batch response body.

    - Single Result-shaped error (no ``batch`` key with list): map via ``http_status_for``.
    - ``batch: []`` and ok: 200
    - All items ok: 200
    - Mixed: **207** Multi-Status
    - All fail: worst status among items
    """
    # Envelope-level Result failure (e.g. too many items)
    batch = envelope.get("batch")
    if not isinstance(batch, list):
        # treat whole body as Result
        return http_status_for(envelope)  # type: ignore[arg-type]

    if envelope.get("ok") and (not batch or all(
        (isinstance(x, Mapping) and x.get("ok", True)) or getattr(x, "ok", True)
        for x in batch
    )):
        return 200

    statuses: list[int] = []
    any_ok = False
    any_err = False
    for item in batch:
        if isinstance(item, Result):
            st = http_status_for(item)
            ok = item.ok
        elif isinstance(item, Mapping):
            st = http_status_for(item)  # type: ignore[arg-type]
            ok = bool(item.get("ok", True))
        else:
            st = DEFAULT_ERROR_STATUS
            ok = False
        statuses.append(st)
        if ok:
            any_ok = True
        else:
            any_err = True

    if not statuses:
        return 200 if envelope.get("ok", True) else DEFAULT_ERROR_STATUS
    if any_ok and any_err:
        return 207  # Multi-Status — partial success
    if any_ok and not any_err:
        return 200
    # all failed — pick most severe
    return min(statuses, key=_severity_rank)


def enrich_batch_envelope(envelope: dict[str, Any]) -> dict[str, Any]:
    """
    Add ``meta`` batch status details and ensure each item has error meta.

    Mutates and returns ``envelope``.
    """
    batch = envelope.get("batch")
    if not isinstance(batch, list):
        # single Result dict
        try:
            r = Result.from_dict(envelope)  # type: ignore[arg-type]
            r = ensure_error_meta(r)
            out = r.to_dict()
            out.setdefault("meta", {})
            out["meta"]["status_mode"] = "envelope_error"
            out["meta"]["http_status"] = http_status_for(r)
            return out
        except Exception:
            envelope.setdefault("meta", {})
            if isinstance(envelope["meta"], dict):
                envelope["meta"]["http_status"] = http_status_for(envelope)
                envelope["meta"]["status_mode"] = "envelope_error"
            return envelope

    ok_count = 0
    err_count = 0
    item_statuses: list[int] = []
    item_codes: list[Optional[str]] = []  # parallel to batch (None if ok)
    codes: list[str] = []  # failed codes in item order
    code_counts: dict[str, int] = {}
    kind_counts: dict[str, int] = {}
    enriched_items: list[dict[str, Any]] = []

    for raw in batch:
        if isinstance(raw, Result):
            item = ensure_error_meta(raw).to_dict()
        elif isinstance(raw, Mapping):
            try:
                item = ensure_error_meta(Result.from_dict(dict(raw))).to_dict()  # type: ignore[arg-type]
            except Exception:
                item = dict(raw)
        else:
            item = {
                "ok": False,
                "ops": [],
                "error": {"code": "internal", "message": "invalid item"},
            }

        st = http_status_for(item)  # type: ignore[arg-type]
        item_statuses.append(st)
        if item.get("ok"):
            ok_count += 1
            item_codes.append(None)
        else:
            err_count += 1
            err = item.get("error") or {}
            code = None
            if isinstance(err, Mapping) and err.get("code"):
                code = str(err["code"])
                codes.append(code)
                code_counts[code] = code_counts.get(code, 0) + 1
                kind = kind_for_code(code)
                kind_counts[kind] = kind_counts.get(kind, 0) + 1
            item_codes.append(code)
        enriched_items.append(item)

    envelope["batch"] = enriched_items
    envelope["ok"] = err_count == 0
    status = batch_http_status(envelope)

    if ok_count and err_count:
        mode = "mixed"
    elif err_count and not ok_count:
        mode = "all_error"
    else:
        mode = "all_ok"

    # worst_code: among failures, lowest severity rank; ties → first in batch order
    worst_code: Optional[str] = None
    worst_kind: Optional[str] = None
    if err_count:
        worst_rank = 10**9
        for i, item in enumerate(enriched_items):
            if item.get("ok"):
                continue
            rank = _severity_rank(item_statuses[i])
            if rank < worst_rank:
                worst_rank = rank
                err = item.get("error") or {}
                worst_code = (
                    str(err["code"])
                    if isinstance(err, Mapping) and err.get("code")
                    else None
                )
                worst_kind = kind_for_code(worst_code) if worst_code else None

    # code → http status (for docs / clients; same as ERROR_HTTP_STATUS lookup)
    code_http: dict[str, int] = {
        c: ERROR_HTTP_STATUS.get(c, DEFAULT_ERROR_STATUS) for c in code_counts
    }

    meta = dict(envelope.get("meta") or {})
    meta.update(
        {
            "batch_size": len(enriched_items),
            "ok_count": ok_count,
            "error_count": err_count,
            "http_status": status,
            "status_mode": mode,
            "item_statuses": item_statuses,
            "item_codes": item_codes,
            "error_codes": codes,
            "code_counts": code_counts,
            "kind_counts": kind_counts,
            "code_http": code_http,
            "worst_code": worst_code,
            "worst_kind": worst_kind,
        }
    )

    envelope["meta"] = meta
    return envelope


def map_batch_error_codes(envelope: Mapping[str, Any]) -> dict[str, Any]:
    """
    Pure summary of error-code mapping for a batch envelope (read-only).

    Returns counts + worst + HTTP implication without mutating the body.
    Prefer ``envelope["meta"]`` after ``enrich_batch_envelope``; this is for
    diagnostics and tests.
    """
    if not isinstance(envelope.get("batch"), list):
        code = None
        err = envelope.get("error")
        if isinstance(err, Mapping):
            code = err.get("code")
        return {
            "status_mode": "envelope_error",
            "http_status": http_status_for(envelope),  # type: ignore[arg-type]
            "worst_code": code,
            "code_counts": {code: 1} if code else {},
        }
    # Re-run enrich on a shallow copy for a clean summary
    import copy

    enriched = enrich_batch_envelope(copy.deepcopy(dict(envelope)))
    m = enriched.get("meta") or {}
    return {
        "status_mode": m.get("status_mode"),
        "http_status": m.get("http_status"),
        "worst_code": m.get("worst_code"),
        "worst_kind": m.get("worst_kind"),
        "code_counts": m.get("code_counts") or {},
        "kind_counts": m.get("kind_counts") or {},
        "code_http": m.get("code_http") or {},
        "item_codes": m.get("item_codes") or [],
        "item_statuses": m.get("item_statuses") or [],
    }
