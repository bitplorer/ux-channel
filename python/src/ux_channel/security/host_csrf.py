"""
Host CSRF forwarding (optional) + stable channel CSRF (**ux-channel** 0.1).

Two layers
----------
1. **Channel CSRF** (protocol, stable)::

       X-Channel: 1

   Server checks only this (``security.channel_header_ok``).

2. **Host CSRF** (framework / **ux-dom**, optional)::

       any token / any header name your ASGI stack expects
       (ux-dom default meta name is often ``X-CSRF-TOKEN``)

   **ux-channel never validates host CSRF.** Clients may *forward* a host
   token so middleware in front of the app still works. Stock
   ``ux-channel.js`` never overwrites the channel header.

Public
------
``from ux_channel.security.host_csrf import intent_headers, host_csrf_meta, CHANNEL_CSRF_HEADER``

Glue (optional): ``ux_channel_ux_dom.csrf`` for meta tags + dual headers.
"""

from __future__ import annotations

import html
import re
from typing import Mapping, Optional, Sequence

__all__ = [
    "CHANNEL_CSRF_HEADER",
    "CHANNEL_CSRF_VALUE",
    "intent_headers",
    "host_csrf_meta",
    "is_channel_csrf_header",
    "looks_like_host_csrf_name",
]

CHANNEL_CSRF_HEADER = "X-Channel"
CHANNEL_CSRF_VALUE = "1"

# Default *forward* spellings when app does not specify (common ASGI/Django/Rails)
_DEFAULT_FORWARD_AS: tuple[str, ...] = ("X-CSRFToken", "X-CSRF-Token")

_HOST_CSRF_NAME = re.compile(r"csrf|xsrf|authenticity.?token", re.I)


def is_channel_csrf_header(name: str) -> bool:
    """True if ``name`` is the stable channel CSRF header (any common casing)."""
    return str(name).lower().replace("_", "-") == "x-channel"


def looks_like_host_csrf_name(name: str) -> bool:
    """DOM discovery heuristic only — not a server trust list."""
    n = str(name or "").strip()
    return bool(n) and not is_channel_csrf_header(n) and bool(_HOST_CSRF_NAME.search(n))


def host_csrf_meta(token: str, *, name: str = "csrf-token") -> str:
    """``<meta name="…" content="…">`` for whatever name the host document wants."""
    return (
        f'<meta name="{html.escape(str(name), quote=True)}" '
        f'content="{html.escape(str(token), quote=True)}"/>'
    )


def intent_headers(
    *,
    host_token: Optional[str] = None,
    forward_as: Sequence[str] = _DEFAULT_FORWARD_AS,
    extra: Optional[Mapping[str, str]] = None,
) -> dict[str, str]:
    """
    Headers for an Intent POST.

    Always ends with ``X-Channel: 1``. Host token is optional and only
    written under ``forward_as`` (never as the channel header).
    ``extra`` cannot clear the channel header.
    """
    token = host_token
    names = tuple(forward_as)

    h: dict[str, str] = {}
    if extra:
        for k, v in dict(extra).items():
            if k is None or v is None or is_channel_csrf_header(str(k)):
                continue
            h[str(k)] = str(v)
    if token:
        for name in names:
            if name and not is_channel_csrf_header(str(name)):
                h[str(name)] = str(token)
    h[CHANNEL_CSRF_HEADER] = CHANNEL_CSRF_VALUE
    return h
