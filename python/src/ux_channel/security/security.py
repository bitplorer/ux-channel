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

import html
import re
import unicodedata
import warnings
from typing import Any, Optional, Sequence
from urllib.parse import urlparse

from ux_channel.render.morph_policy import apply_morph_policy

# Schemes blocked in navigate / push_url / set_attr URL attributes (XSS / drive-by)
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

# Attributes whose values are URLs. ``data-*`` is not in this set; only the
# exact ``data`` attribute (object URLs) is. Names are compared case-insensitively.
_URL_ATTRS = frozenset(
    {
        "action",
        "archive",
        "background",
        "cite",
        "classid",
        "code",
        "codebase",
        "data",
        "dynsrc",
        "formaction",
        "href",
        "icon",
        "longdesc",
        "lowsrc",
        "manifest",
        "ping",
        "poster",
        "profile",
        "src",
        "usemap",
    }
)


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
    Return href if safe for navigate/push_url and set_attr URL attributes, else None.

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


# data:image types a browser can paint in img/src without running markup.
_SAFE_IMAGE_DATA_RE = re.compile(
    r"^data:image/(png|jpeg|gif|webp|avif)(?:$|[;,])",
    re.IGNORECASE,
)


def _is_src_type_attr(name: object) -> bool:
    """True for ``src`` and names ending in ``:src``. ``poster`` is not src-type."""
    if not isinstance(name, str):
        return False
    token = name.strip().lower()
    return token == "src" or token.endswith(":src")


def _url_attr_exception(name: object, value: str) -> bool:
    """Kept URLs that ``safe_href`` rejects: ``//`` and src image/blob."""
    cleaned = _strip_href_controls(value).strip()
    if cleaned.startswith("//"):
        return True
    if not _is_src_type_attr(name):
        return False
    if cleaned.lower().startswith("blob:"):
        return True
    return _SAFE_IMAGE_DATA_RE.match(cleaned) is not None


def _is_url_attr(name: object) -> bool:
    """True for href/src/action/formaction/xlink:href and the other URL attributes."""
    if not isinstance(name, str):
        return False
    token = name.strip().lower()
    if token in _URL_ATTRS:
        return True
    return token.endswith(":href") or token.endswith(":src")


def _unsafe_url_attr(name: object, value: str) -> bool:
    """True when a non-empty URL form of ``value`` is refused for ``name``.

    HTML entities are decoded (twice, so ``&#38;#106;`` collapses) before the
    scheme check. Empty and whitespace-only strings are not script URLs.
    Protocol-relative ``//`` URLs are kept. On src-type attributes, ``blob:``
    and ``data:image/png|jpeg|gif|webp|avif`` are kept. ``data:image/svg+xml``
    and ``data:text/html`` are refused on every attribute.
    """
    current = value
    seen: list[str] = []
    refused = False
    for _ in range(3):
        if current in seen:
            break
        seen.append(current)
        if _url_attr_exception(name, current):
            return False
        if safe_href(current) is None and current.strip():
            refused = True
        decoded = html.unescape(current)
        if decoded == current:
            break
        current = decoded
    return refused


def _dom_attr_string(value: Any) -> str:
    """String form ``setAttribute`` uses for a non-None value.

    Lists and tuples join with ``,`` (WebIDL ``ToString`` on an array).
    Booleans are ``true`` / ``false``. Everything else uses ``str``.
    """
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (list, tuple)):
        parts = ["" if item is None else _dom_attr_string(item) for item in value]
        return ",".join(parts)
    return str(value)


def _sanitize_url_attr_value(name: object, value: Any) -> tuple[bool, Any]:
    """Return ``(keep, value)`` for one URL attribute.

    ``None`` removes the attribute. Every other value is turned into a string
    the way ``setAttribute`` does, then checked, so a list or other object
    cannot skip the scheme check. Script schemes and every other non-empty
    value ``safe_href`` rejects are dropped. Allowed strings are the
    ``safe_href``-normalized form. Empty and whitespace-only strings are kept
    as authored.
    """
    if value is None:
        return True, None
    text = value if isinstance(value, str) else _dom_attr_string(value)
    if _unsafe_url_attr(name, text):
        return False, None
    normalized = safe_href(text)
    if normalized is None:
        return True, text
    return True, normalized


def _sanitize_attr_map(attrs: dict) -> dict | None:
    """Drop unsafe URL attributes. ``None`` means the whole map was refused."""
    cleaned: dict[Any, Any] = {}
    for key, value in attrs.items():
        if _is_url_attr(key):
            keep, safe_value = _sanitize_url_attr_value(key, value)
            if not keep:
                continue
            cleaned[key] = safe_value
        else:
            cleaned[key] = value
    if attrs and not cleaned:
        return None
    return cleaned


def _as_op_dict(op: Any) -> Any:
    """Mapping form of an op. Objects with ``to_dict`` are converted."""
    if isinstance(op, dict):
        return op
    to_dict = getattr(op, "to_dict", None)
    if not callable(to_dict):
        return op
    try:
        body = to_dict()
    except Exception:
        return op
    return body if isinstance(body, dict) else op


def _sanitize_one(op: Any, allowed_hosts: tuple[str, ...] | list[str] | None) -> Any:
    """Href-check one op and every op nested under ``ops``."""
    op = _as_op_dict(op)
    if not isinstance(op, dict):
        return op
    name = op.get("op")
    if name == "set_attr" and isinstance(op.get("attrs"), dict):
        cleaned = _sanitize_attr_map(op["attrs"])
        if cleaned is None:
            op = {
                "op": "noop",
                "meta": {"dropped": "set_attr", "reason": "unsafe_href"},
            }
        else:
            op = dict(op)
            op["attrs"] = cleaned
    elif name in ("navigate", "push_url", "redirect"):
        href = op.get("href")
        safe = safe_href(
            href if isinstance(href, str) else None,
            allowed_hosts=allowed_hosts,
        )
        if safe is None:
            op = {"op": "noop", "meta": {"dropped": name, "reason": "unsafe_href"}}
        else:
            op = dict(op)
            op["href"] = safe
    nested = op.get("ops")
    if isinstance(nested, list):
        op = dict(op)
        op["ops"] = [_sanitize_one(child, allowed_hosts) for child in nested]
    return op


def sanitize_op_hrefs(
    ops: list,
    *,
    allowed_hosts: tuple[str, ...] | list[str] | None = None,
) -> list:
    """Drop unsafe navigate/push_url hrefs and set_attr URL attributes.

    Walks ``seq``, ``timer.set``, ``invoke``, and any other op that carries
    an ``ops`` list.
    """
    return [_sanitize_one(op, allowed_hosts) for op in ops]


def filter_outbound_ops(
    ops: list,
    *,
    policy: str = "off",
    allowed_hosts: tuple[str, ...] | list[str] | None = None,
) -> list:
    """Href-check ops, then apply the morph/swap/toast policy.

    Action dispatch and ``PushBus.publish`` both go through this function.
    """
    cleaned = sanitize_op_hrefs(list(ops), allowed_hosts=allowed_hosts)
    return apply_morph_policy(cleaned, policy=policy)


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


