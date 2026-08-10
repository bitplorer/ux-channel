"""
Shared HTTP preflight for POST /action — one policy for FastAPI + Starlette.

Keeps security checks (body size, origin, channel header, client version, IP
rate limit) in a single pure module so hosts cannot drift.
"""

from __future__ import annotations

from typing import Any, Mapping, Optional, Tuple

from ux_channel.transport.middleware import check_client_version
from ux_channel.security.security import channel_header_ok, content_length_ok, origin_allowed
from ux_channel.protocol.types import Result

# (Result, http_status, optional_extra_headers)
PreflightFail = Tuple[Result, int, list[tuple[bytes, bytes]]]


def preflight_action(
    headers: Mapping[str, str],
    *,
    config: Any = None,
    ip_limiter: Any = None,
    client_ip: str = "unknown",
    trusted_proxy: bool = False,
) -> Optional[PreflightFail]:
    """
    Run shared action preflight. Return ``None`` if the request may proceed.

    ``headers`` should be a case-insensitive or lowercased mapping of
    header name → value (string).
    """
    # normalize
    h = {str(k).lower(): str(v) for k, v in headers.items()}

    max_request = int(getattr(config, "max_request_bytes", 256_000) or 256_000)
    allowed_origins = tuple(getattr(config, "allowed_origins", ()) or ())
    enforce_same = bool(getattr(config, "enforce_same_origin", True))
    require_ch = bool(getattr(config, "require_channel_header", True))

    cl = h.get("content-length")
    if not content_length_ok(cl, max_request):
        return (
            Result.failure("payload_too_large", "request too large"),
            413,
            [],
        )

    origin = h.get("origin")
    host = h.get("host")
    if not origin_allowed(
        origin,
        allowed_origins=allowed_origins,
        enforce_same_origin=enforce_same,
        request_host=host,
    ):
        try:
            from ux_channel.security.security_events import emit_security
            emit_security("http_origin_deny", reason="origin not allowed", client=str(origin or ""))
        except Exception:
            pass
        return Result.failure("forbidden", "origin not allowed"), 403, []

    ctype = (h.get("content-type") or "").lower()
    if not channel_header_ok(h, required=require_ch, content_type=ctype):
        try:
            from ux_channel.security.security_events import emit_security
            emit_security("http_csrf_deny", reason="missing X-Channel header")
        except Exception:
            pass
        return (
            Result.failure("forbidden", "missing X-Channel header"),
            403,
            [],
        )

    min_client = getattr(config, "min_client_version", None) if config else None
    if min_client:
        cv = h.get("x-channel-client-version")
        err = check_client_version(cv, min_version=str(min_client))
        if err:
            return (
                Result.failure("upgrade_required", err, retryable=False),
                426,
                [],
            )

    if ip_limiter is not None:
        ip = client_ip or "unknown"
        if trusted_proxy and h.get("x-forwarded-for"):
            ip = h["x-forwarded-for"].split(",")[0].strip()
        if not ip_limiter.allow(f"ip:{ip}"):
            try:
                from ux_channel.security.security_events import emit_security
                emit_security("http_rate_limit", reason="Too many requests", client=str(ip))
            except Exception:
                pass
            return (
                Result.failure("rate_limited", "Too many requests", retryable=True, retry_after=5),
                429,
                [(b"retry-after", b"5")],
            )

    return None


def headers_from_starlette(request_headers: Any) -> dict[str, str]:
    """Convert Starlette/FastAPI Headers to a plain dict."""
    try:
        return {k.lower(): v for k, v in request_headers.items()}
    except Exception:
        return {str(k).lower(): str(v) for k, v in dict(request_headers).items()}
