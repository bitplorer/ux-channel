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
import logging
import re
import unicodedata
import warnings
from typing import Any, Optional, Sequence
from urllib.parse import urlparse

from ux_channel.render.morph_policy import apply_morph_policy

logger = logging.getLogger("ux_channel.security.security")

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


def _strip_url_noise(text: str) -> str:
    """Drop C0, C1, DEL, U+FFFD, and whitespace before a scheme check.

    This is the only strip the scheme decision uses. html5lib rewrites
    U+0000 to U+FFFD before a scrubber sees the attribute, and a browser
    ignores these characters inside the token (``java\\x00script:``,
    ``jav\\tscript:``, leading spaces). A kept URL does not use this
    form: path spaces stay in ``_stored_href``.
    """
    kept: list[str] = []
    for ch in text:
        if ch == "\ufffd" or ch.isspace():
            continue
        if unicodedata.category(ch).startswith(("C", "Z")):
            continue
        kept.append(ch)
    return "".join(kept)


def _strip_href_controls(text: str) -> str:
    """Drop C0/C1/DEL and U+FFFD. Spaces in a kept URL stay."""
    return "".join(
        ch
        for ch in text
        if ch != "\ufffd" and not unicodedata.category(ch).startswith("C")
    )


def _scheme_token(text: str) -> str:
    """Scheme token with whitespace removed (browsers ignore it there)."""
    return "".join(
        ch
        for ch in text
        if not ch.isspace() and not unicodedata.category(ch).startswith("Z")
    )


def _stored_href(href: str) -> str | None:
    """Kept URL: controls and U+FFFD removed, scheme whitespace collapsed.

    Spaces outside the scheme token stay. The scheme decision already
    happened on ``_strip_url_noise`` and must not be repeated here.
    """
    h = _strip_href_controls(href).strip()
    if not h:
        return None
    path = h.split("?", 1)[0].split("#", 1)[0]
    if ":" not in path:
        return h
    pre, _sep, rest = h.partition(":")
    scheme = _scheme_token(pre)
    if scheme != pre:
        h = scheme + ":" + rest
    return h


def safe_href(
    href: str | None,
    *,
    allowed_hosts: tuple[str, ...] | list[str] | None = None,
) -> str | None:
    """
    Return href if safe for navigate/push_url and set_attr URL attributes, else None.

    Allows: relative paths, http(s), mailto, tel, and hash/query-only.
    Blocks: javascript:, data:, vbscript:, file:, etc.

    The scheme decision strips leading and embedded C0 controls, DEL,
    U+FFFD (html5lib's stand-in for NUL), and whitespace, then refuses
    ``javascript:``, ``vbscript:``, ``data:``, and the other blocked
    schemes. The returned value still keeps spaces that were not in the
    scheme token, and drops the controls.

    If ``allowed_hosts`` is non-empty, absolute http(s) URLs must match
    host (or subdomain of) an allowlisted host (Wave 1 open-redirect control).
    """
    if href is None:
        return None
    if not isinstance(href, str):
        return None
    # Scheme decision. ``_strip_url_noise`` is the only strip here, so a
    # browser-ignored character cannot hide ``javascript:``.
    checked = _strip_url_noise(href)
    if not checked:
        return None
    if checked.startswith("//") or checked.startswith("\\") or checked.startswith("/\\"):
        return None
    path = checked.split("?", 1)[0].split("#", 1)[0]
    if ":" in path:
        scheme_l = checked.partition(":")[0].lower()
        if scheme_l in _BLOCKED_HREF_SCHEMES:
            return None
        if scheme_l not in ("http", "https", "mailto", "tel"):
            if re.match(r"^[a-z][a-z0-9+.-]*:", checked.lower()):
                return None
        hosts = tuple(allowed_hosts or ())
        if hosts and scheme_l in ("http", "https"):
            host = (urlparse(checked).hostname or "").lower()
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
    return _stored_href(href)


def _host_on_list(host: str, allowed_hosts: tuple[str, ...] | list[str] | None) -> bool:
    """True when ``host`` is an allowlisted host or its subdomain."""
    if not host:
        return False
    for allowed in tuple(allowed_hosts or ()):
        name = str(allowed).lower().lstrip(".")
        if host == name or host.endswith("." + name):
            return True
    return False


def _request_hostname(origin_host: str | None) -> str:
    """Hostname from a ``Host`` header. The port is not part of the name."""
    if not origin_host:
        return ""
    text = origin_host.strip().lower()
    if text.startswith("["):
        end = text.find("]")
        return text[1:end] if end > 1 else ""
    return text.split(":", 1)[0]


def _navigate_href(
    href: str | None,
    *,
    policy: str,
    allowed_hosts: tuple[str, ...] | list[str] | None,
    origin_host: str | None,
) -> str | None:
    """Href kept for navigate, push_url, and redirect.

    ``off`` is ``safe_href``. Strict also refuses an absolute http(s) URL
    unless its host is the request host or on ``allowed_hosts``. A push has
    no request, so only the allowlist can keep an absolute URL.
    """
    if policy != "strict":
        return safe_href(href, allowed_hosts=allowed_hosts)
    if href is None or not isinstance(href, str):
        return None
    # urlparse treats ``\`` and an empty authority differently from a browser.
    # Refuse those shapes before any host comparison.
    if _navigate_forbidden(href):
        return None
    safe = safe_href(href, allowed_hosts=())
    if safe is None:
        return None
    path = safe.split("?", 1)[0].split("#", 1)[0]
    origin = _request_hostname(origin_host)
    if ":" not in path:
        if not origin and not _single_slash_path(safe):
            return None
        return safe
    scheme, _sep, rest = safe.partition(":")
    scheme_l = _scheme_token(scheme).lower()
    if scheme_l not in ("http", "https"):
        return safe
    host = _http_host(rest)
    if host is None or host == "":
        return None
    if _host_on_list(host, allowed_hosts) or (origin and host == origin):
        return safe
    return None


def _navigate_forbidden(href: str) -> bool:
    """Backslash, tab, newline, or any other control character."""
    for ch in href:
        if ch == "\\":
            return True
        if unicodedata.category(ch).startswith("C"):
            return True
    return False


def _single_slash_path(href: str) -> bool:
    """A same-site path. ``//`` and ``/\\`` are not relative."""
    if not href.startswith("/"):
        return False
    if href.startswith("//") or href.startswith("/\\"):
        return False
    return True


def _http_host(rest: str) -> str | None:
    """Host after an http(s) scheme, or None when the authority is not ``//host``.

    ``http:evil.test/`` and ``https:///evil.test/`` are not ``scheme://host``.
    An empty host is ``""`` so the caller can refuse it.
    """
    if not rest.startswith("//"):
        return None
    authority = rest[2:].split("/", 1)[0].split("?", 1)[0].split("#", 1)[0]
    if authority.startswith("@"):
        return ""
    if "@" in authority:
        authority = authority.split("@", 1)[0]
    if authority.startswith("["):
        end = authority.find("]")
        host = authority[1:end] if end > 1 else ""
    else:
        host = authority.split(":", 1)[0]
    return host.strip().lower()


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
    """Kept URLs that ``safe_href`` rejects: ``//`` and src image/blob.

    The ``//`` exception is a whitespace trim only. Stripping control
    characters first would keep ``\\x01//x`` and ``/\\t/x``, which the
    client refuses.
    """
    if value.strip().startswith("//"):
        return True
    cleaned = _strip_href_controls(value).strip()
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

    ``None`` removes the attribute. A dict or a list is refused and is not
    stringified. Every other non-string is turned into a string the way
    ``setAttribute`` does, then checked. Script schemes and every other
    non-empty value ``safe_href`` rejects are dropped. Allowed strings are
    the ``safe_href``-normalized form. Empty and whitespace-only strings are
    kept as authored.
    """
    if value is None:
        return True, None
    if isinstance(value, (list, tuple, dict)):
        return False, None
    text = value if isinstance(value, str) else _dom_attr_string(value)
    if _unsafe_url_attr(name, text):
        return False, None
    normalized = safe_href(text)
    if normalized is None:
        return True, text
    return True, normalized


def _event_or_srcdoc(name: object) -> bool:
    """True for event-handler names (``on*``) and ``srcdoc``."""
    if not isinstance(name, str):
        return False
    token = name.strip().lower()
    if token == "srcdoc":
        return True
    return len(token) > 2 and token.startswith("on")


def _sanitize_attr_map(attrs: dict) -> tuple[dict | None, str]:
    """Return ``(attrs, reason)``. ``None`` attrs means the op is a noop.

    ``unsafe_attr`` refuses the whole op: an ``on*`` name or ``srcdoc``.
    Markup is not a JavaScript trust marker, so ``__html__`` does not opt in.
    ``unsafe_href`` means every attribute was an unsafe URL.
    """
    cleaned: dict[Any, Any] = {}
    for key, value in attrs.items():
        if _event_or_srcdoc(key):
            return None, "unsafe_attr"
        if isinstance(value, (list, tuple, dict)):
            continue
        if _is_url_attr(key):
            keep, safe_value = _sanitize_url_attr_value(key, value)
            if not keep:
                continue
            cleaned[key] = safe_value
        else:
            cleaned[key] = value
    if attrs and not cleaned:
        return None, "unsafe_href"
    return cleaned, ""


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
        logger.error("outbound op to_dict failed")
        return {"op": "noop", "meta": {"dropped": "to_dict"}}
    return body if isinstance(body, dict) else op


def _sanitize_one(
    op: Any,
    allowed_hosts: tuple[str, ...] | list[str] | None,
    *,
    policy: str = "off",
    origin_host: str | None = None,
) -> Any:
    """Href-check one op and every op nested under ``ops``."""
    op = _as_op_dict(op)
    if not isinstance(op, dict):
        return op
    name = op.get("op")
    if name == "set_attr" and isinstance(op.get("attrs"), dict):
        cleaned, reason = _sanitize_attr_map(op["attrs"])
        if cleaned is None:
            op = {
                "op": "noop",
                "meta": {"dropped": "set_attr", "reason": reason or "unsafe_href"},
            }
        else:
            op = dict(op)
            op["attrs"] = cleaned
    elif name in ("navigate", "push_url", "redirect"):
        href = op.get("href")
        safe = _navigate_href(
            href if isinstance(href, str) else None,
            policy=policy,
            allowed_hosts=allowed_hosts,
            origin_host=origin_host,
        )
        if safe is None:
            op = {"op": "noop", "meta": {"dropped": name, "reason": "unsafe_href"}}
        else:
            op = dict(op)
            op["href"] = safe
    nested = op.get("ops")
    if isinstance(nested, list):
        op = dict(op)
        op["ops"] = [
            _sanitize_one(child, allowed_hosts, policy=policy, origin_host=origin_host)
            for child in nested
        ]
    return op


def sanitize_op_hrefs(
    ops: list,
    *,
    allowed_hosts: tuple[str, ...] | list[str] | None = None,
    policy: str = "off",
    origin_host: str | None = None,
) -> list:
    """Drop unsafe navigate/push_url hrefs and set_attr URL attributes.

    Walks ``seq``, ``timer.set``, ``invoke``, and any other op that carries
    an ``ops`` list. ``policy="off"`` keeps the historical ``safe_href`` rule.
    """
    return [
        _sanitize_one(op, allowed_hosts, policy=policy, origin_host=origin_host)
        for op in ops
    ]


def filter_outbound_ops(
    ops: list,
    *,
    policy: str = "off",
    allowed_hosts: tuple[str, ...] | list[str] | None = None,
    origin_host: str | None = None,
) -> list:
    """Href-check ops, then apply the morph/swap/toast policy.

    Action dispatch and ``PushBus.publish`` both go through this function.
    Strict navigate is same-origin (``origin_host``) or ``allowed_hosts``.
    """
    cleaned = sanitize_op_hrefs(
        list(ops),
        allowed_hosts=allowed_hosts,
        policy=policy,
        origin_host=origin_host,
    )
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


