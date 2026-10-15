"""
HTTP-layer and apply-op security helpers (hardened after adversarial review).

Surfaces covered:
  - Origin / CSRF class checks
  - Channel header requirement for JSON POSTs
  - Request size
  - Safe navigation href schemes
  - Action name hygiene
"""

from __future__ import annotations

import re
import unicodedata
import warnings
from typing import Optional, Sequence
from urllib.parse import urlparse

# Schemes blocked in navigate / push_url (XSS / drive-by)
_BLOCKED_HREF_SCHEMES = frozenset(
    {
        "javascript",
        "data",
        "vbscript",
        "file",
        "blob",
        "jar",
    }
)

# Action names: dotted identifiers, limited length (DoS / log injection)
_ACTION_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*(\.[A-Za-z0-9_]+)*$")
MAX_ACTION_NAME_LEN = 128


def origin_allowed(
    origin: Optional[str],
    *,
    allowed_origins: Sequence[str],
    enforce_same_origin: bool,
    request_host: Optional[str] = None,
) -> bool:
    """
    Return True if the request Origin is acceptable.

    Rules
    -----
    - Missing Origin: allow (non-browser clients; pair with require_channel_header)
    - Origin literal \"null\" (sandboxed iframe): **deny**
    - allowed_origins non-empty: exact match required
    - enforce_same_origin: Origin host must match request Host (hostname)
    """
    if not origin:
        return True
    if origin.strip().lower() == "null":
        return False
    if allowed_origins:
        return origin in allowed_origins
    if enforce_same_origin and request_host:
        try:
            parsed = urlparse(origin)
            ohost = parsed.hostname
        except Exception:
            return False
        if not ohost:
            return False
        # Host header: hostname[:port]
        rh = request_host.split(":")[0].strip().lower()
        return ohost.lower() == rh
    return True


def content_length_ok(content_length: Optional[str], max_bytes: int) -> bool:
    """Reject clearly oversized Content-Length before reading body."""
    if content_length is None or content_length == "":
        return True
    try:
        n = int(content_length)
    except ValueError:
        return False
    return 0 <= n <= max_bytes


def channel_header_ok(
    headers: dict | Any,
    *,
    required: bool,
    content_type: str = "",
) -> bool:
    """
    For JSON Channel posts, require X-Channel: 1 (CSRF mitigation).

    Browsers' cross-site form posts cannot set custom headers easily;
    fetch() from our client always sets the header.
    Form-urlencoded progressive enhance is exempt.

    Orthogonal to host/framework CSRF (any meta/header name). Presence of a
    framework token does **not** satisfy this check; both may be sent.
    See ``ux_channel.host_csrf``.
    """
    if not required:
        return True
    ct = (content_type or "").lower()
    if "application/x-www-form-urlencoded" in ct or "multipart/form-data" in ct:
        return True
    # headers may be Starlette Headers or dict
    def _get(name: str) -> str:
        if hasattr(headers, "get"):
            v = headers.get(name) or headers.get(name.lower())
            return str(v) if v is not None else ""
        return ""

    val = _get("x-channel") or _get("X-Channel")
    return val.strip() in ("1", "true", "yes")


def _strip_href_controls(text: str) -> str:
    """Drop C0/C1 controls and other Unicode 'C' characters (NUL, tab, DEL)."""
    return "".join(
        ch for ch in text if not unicodedata.category(ch).startswith("C")
    )


def _scheme_token(text: str) -> str:
    """Scheme token with whitespace removed (browsers ignore it there)."""
    return "".join(
        ch
        for ch in text
        if not ch.isspace() and not unicodedata.category(ch).startswith("Z")
    )


def safe_href(
    href: str | None,
    *,
    allowed_hosts: tuple[str, ...] | list[str] | None = None,
) -> str | None:
    """
    Return href if safe for navigate/push_url, else None.

    Allows: relative paths, http(s), mailto, tel, and hash/query-only.
    Blocks: javascript:, data:, vbscript:, file:, etc.

    Control characters are removed and whitespace inside the scheme token
    is collapsed before the scheme check, so ``java\\x00script:`` and
    ``java script:`` cannot bypass the block. The returned value is that
    normalized string when the URL is allowed.

    If ``allowed_hosts`` is non-empty, absolute http(s) URLs must match
    host (or subdomain of) an allowlisted host (Wave 1 open-redirect control).
    """
    if href is None:
        return None
    if not isinstance(href, str):
        return None
    h = _strip_href_controls(href).strip()
    if not h:
        return None
    # protocol-relative //evil.com — treat as blocked for navigate (open redirect risk)
    if h.startswith("//"):
        return None
    # Windows/UNC-ish or escaped backslash openers
    if h.startswith("\\") or h.startswith("/\\"):
        return None
    # scheme present?
    path = h.split("?", 1)[0].split("#", 1)[0]
    if ":" in path:
        pre, _sep, rest = h.partition(":")
        scheme = _scheme_token(pre)
        if scheme != pre:
            h = scheme + ":" + rest
        scheme_l = scheme.lower()
        lower = h.lower()
        # allow http https mailto tel
        if scheme_l in _BLOCKED_HREF_SCHEMES:
            return None
        if scheme_l not in ("http", "https", "mailto", "tel"):
            # relative with colon in path is rare; block unknown schemes
            if re.match(r"^[a-z][a-z0-9+.-]*:", lower):
                return None
        # host allowlist for absolute http(s)
        hosts = tuple(allowed_hosts or ())
        if hosts and scheme_l in ("http", "https"):
            host = (urlparse(h).hostname or "").lower()
            if not host:
                return None
            ok = False
            for allowed in hosts:
                a = allowed.lower().lstrip(".")
                if host == a or host.endswith("." + a):
                    ok = True
                    break
            if not ok:
                return None
    return h


def sanitize_op_hrefs(
    ops: list,
    *,
    allowed_hosts: tuple[str, ...] | list[str] | None = None,
) -> list:
    """Filter/block dangerous hrefs in navigate/push_url ops (defense in depth)."""
    out = []
    for op in ops:
        if not isinstance(op, dict):
            out.append(op)
            continue
        name = op.get("op")
        if name in ("navigate", "push_url", "redirect"):
            href = op.get("href")
            safe = safe_href(
                href if isinstance(href, str) else None,
                allowed_hosts=allowed_hosts,
            )
            if safe is None:
                # convert to noop toast-less drop
                out.append({"op": "noop", "meta": {"dropped": name, "reason": "unsafe_href"}})
                continue
            op = dict(op)
            op["href"] = safe
        out.append(op)
    return out


def validate_action_name(action: str) -> str:
    """Raise ValueError if action name is illegal."""
    if not action or not isinstance(action, str):
        raise ValueError("action name required")
    if len(action) > MAX_ACTION_NAME_LEN:
        raise ValueError(f"action name too long (max {MAX_ACTION_NAME_LEN})")
    if "\x00" in action or "\n" in action or "\r" in action:
        raise ValueError("action name contains illegal characters")
    if not _ACTION_RE.match(action):
        raise ValueError(
            "action name must be dotted identifiers (e.g. Orders.place)"
        )
    return action


def warn_trusted_proxy(enabled: bool) -> None:
    if enabled:
        warnings.warn(
            "trusted_proxy=True trusts X-Forwarded-For from the client. "
            "Only enable behind a reverse proxy that overwrites XFF.",
            stacklevel=3,
        )


# typing Any
from typing import Any  # noqa: E402
