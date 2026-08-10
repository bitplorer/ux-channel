# Copyright (c) 2026 UX-CHANNEL
#
# This software is released under the MIT License.
# https://opensource.org/licenses/MIT
"""Wire plane — encode/decode Intent & Result.

Public API (app developers)::

    from ux_channel.wire import encode, decode, dumps, loads, configure_wire

    configure_wire(format="json", engine="auto")  # default
    blob = encode(result)                         # or format="cxb"
    doc = decode(blob.data)

Formats: ``json`` (default) · ``msgpack`` · ``cbor`` · ``cxb``.
CXB is built-in; optional ``_cxb_native`` is used automatically when present.

Codec authors (internal plugins): ``ux_channel.wire.plugins``.

Env: ``UX_CHANNEL_WIRE``, ``UX_CHANNEL_WIRE_ENGINE``, ``UX_CHANNEL_WIRE_WORKERS``.
"""

from __future__ import annotations

from ux_channel.wire.core import (
    MEDIA_TYPES,
    Codec,
    WireBlob,
    WirePolicy,
    available_engines,
    available_formats,
    clear_codec_cache,
    configure_wire,
    decode,
    decode_complete,
    decode_many,
    dumps,
    dumps_bytes,
    encode,
    encode_many,
    get_batch_workers,
    get_codec,
    get_policy,
    loads,
    loads_bytes,
    reset_wire,
    set_batch_workers,
    size_of,
    try_decode,
)
from ux_channel.wire.negotiate import (
    decode_http_body,
    encode_http_body,
    negotiate_request,
    negotiate_response,
    parse_accept,
    response_headers_for,
)

__all__ = [
    "MEDIA_TYPES",
    "Codec",
    "WireBlob",
    "WirePolicy",
    "available_engines",
    "available_formats",
    "clear_codec_cache",
    "configure_wire",
    "decode",
    "decode_complete",
    "decode_http_body",
    "decode_many",
    "dumps",
    "dumps_bytes",
    "encode",
    "encode_http_body",
    "encode_many",
    "get_batch_workers",
    "get_codec",
    "get_policy",
    "loads",
    "loads_bytes",
    "negotiate_request",
    "negotiate_response",
    "parse_accept",
    "reset_wire",
    "response_headers_for",
    "set_batch_workers",
    "size_of",
    "try_decode",
]
