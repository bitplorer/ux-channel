# Copyright (c) 2026 UX-CHANNEL
#
# This software is released under the MIT License.
# https://opensource.org/licenses/MIT
"""HTTP Accept / Content-Type negotiation and body encode/decode."""

from __future__ import annotations

from typing import Any

from ux_channel.wire.core import (
    WireBlob,
    available_formats,
    decode,
    encode,
    format_from_media_type,
    get_policy,
)

__all__ = [
    "parse_accept",
    "negotiate_request",
    "negotiate_response",
    "decode_http_body",
    "encode_http_body",
    "response_headers_for",
]


def parse_accept(accept: str | None) -> list[str]:
    """Accept header → ordered format names."""
    if not accept:
        return []
    out: list[str] = []
    for part in accept.split(","):
        mt = part.split(";")[0].strip().lower()
        if not mt or mt == "*/*":
            continue
        fmt = format_from_media_type(mt)
        if fmt and fmt not in out:
            out.append(fmt)
    return out


def negotiate_request(content_type: str | None) -> str:
    """Preferred request body format."""
    fmt = format_from_media_type(content_type)
    if fmt and fmt in available_formats():
        return fmt
    return "json"


def negotiate_response(
    accept: str | None,
    *,
    prefer_policy: bool = True,
) -> str:
    """Preferred response format."""
    available = set(available_formats())
    for fmt in parse_accept(accept):
        if fmt in available:
            return fmt
    if prefer_policy:
        pol = get_policy().format
        if pol in available:
            return pol
    return "json"


def decode_http_body(
    raw: bytes,
    *,
    content_type: str | None = None,
    complete: bool = True,
) -> Any:
    """Decode HTTP body (complete recovery by default)."""
    if not raw:
        return {}
    return decode(raw, format=negotiate_request(content_type), complete=complete)


def encode_http_body(
    obj: Any,
    *,
    accept: str | None = None,
    content_type_in: str | None = None,
    pretty: bool = False,
    complete: bool = True,
) -> WireBlob:
    """Encode response: Accept → echo Content-Type → policy → JSON."""
    available = set(available_formats())
    preferred = None
    for fmt in parse_accept(accept):
        if fmt in available:
            preferred = fmt
            break
    if preferred is None:
        req_fmt = format_from_media_type(content_type_in)
        if req_fmt and req_fmt in available:
            preferred = req_fmt
    if preferred is None:
        preferred = negotiate_response(accept)
    return encode(obj, format=preferred, pretty=pretty, complete=complete)


def response_headers_for(blob: WireBlob) -> dict[str, str]:
    """Headers describing wire format (and fallback if used)."""
    h = {
        "X-Channel-Wire": blob.format,
        "Content-Type": blob.media_type,
    }
    if blob.fallback:
        h["X-Channel-Wire-Fallback"] = "1"
        if blob.preferred_format:
            h["X-Channel-Wire-Preferred"] = blob.preferred_format
    return h
