"""ux-dom convenience wrappers over ``ux_channel.host_csrf``."""

from __future__ import annotations

from typing import Mapping, Optional, Sequence

from ux_channel.security.host_csrf import (
    CHANNEL_CSRF_HEADER,
    CHANNEL_CSRF_VALUE,
    host_csrf_meta,
    intent_headers,
    is_channel_csrf_header,
)

__all__ = [
    "UX_DOM_CSRF_META_NAME",
    "CHANNEL_CSRF_HEADER",
    "CHANNEL_CSRF_VALUE",
    "ux_dom_csrf_meta",
    "channel_and_ux_dom_headers",
    "assert_csrf_names_do_not_collide",
    "intent_headers",
]

# Default meta name used by many ux-dom hosts (not part of channel CSRF)
UX_DOM_CSRF_META_NAME = "X-CSRF-TOKEN"


def ux_dom_csrf_meta(token: str, *, name: str = UX_DOM_CSRF_META_NAME) -> str:
    return host_csrf_meta(token, name=name)


def channel_and_ux_dom_headers(
    *,
    host_token: Optional[str] = None,
    forward_as: Sequence[str] = (UX_DOM_CSRF_META_NAME,),
    extra: Optional[Mapping[str, str]] = None,
) -> dict[str, str]:
    """Build Intent headers: optional host token + required ``X-Channel: 1``."""
    return intent_headers(host_token=host_token, forward_as=forward_as, extra=extra)


def assert_csrf_names_do_not_collide(
    host_header_names: Sequence[str] = (UX_DOM_CSRF_META_NAME,),
) -> None:
    for n in host_header_names:
        if is_channel_csrf_header(n):
            raise ValueError(
                f"host CSRF name {n!r} collides with channel CSRF header "
                f"{CHANNEL_CSRF_HEADER!r}"
            )
