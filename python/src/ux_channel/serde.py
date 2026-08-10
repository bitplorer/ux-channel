# Copyright (c) 2026 UX-CHANNEL
#
# This software is released under the MIT License.
# https://opensource.org/licenses/MIT
"""JSON helpers — thin re-export of ``ux_channel.wire`` dumps/loads.

Prefer ``ux_channel.wire`` when selecting formats (json/msgpack/cxb).
"""

from __future__ import annotations

from ux_channel.wire import (
    MEDIA_TYPES,
    Codec,
    WireBlob,
    WirePolicy,
    available_engines,
    available_formats,
    configure_wire,
    dumps,
    dumps_bytes,
    get_codec,
    get_policy,
    loads,
    loads_bytes,
    reset_wire,
    size_of,
)

__all__ = [
    "MEDIA_TYPES",
    "Codec",
    "WireBlob",
    "WirePolicy",
    "available_engines",
    "available_formats",
    "configure_wire",
    "dumps",
    "dumps_bytes",
    "get_codec",
    "get_policy",
    "loads",
    "loads_bytes",
    "reset_wire",
    "size_of",
]
