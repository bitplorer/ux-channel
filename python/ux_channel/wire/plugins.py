# Copyright (c) 2026 UX-CHANNEL
#
# This software is released under the MIT License.
# https://opensource.org/licenses/MIT
"""Internal wire **format plugin** registry.

**App developers:** do not use this module. Prefer::

    from ux_channel.wire import encode, decode, configure_wire
    encode(doc, format="cxb")   # CXB is automatic (native when installed)

**Codec developers** (new formats / experimental accelerators)::

    from ux_channel.wire.plugins import register_wire_format

CXB itself is bootstrapped at import; hosts never register it for normal use.
Optional ``ux_channel._cxb_native`` is picked up automatically by CXB encode/decode.
"""

from __future__ import annotations

from ux_channel.wire.core import (
    WireFormatPlugin,
    list_wire_plugins,
    register_wire_format,
    unregister_wire_format,
)

__all__ = [
    "WireFormatPlugin",
    "list_wire_plugins",
    "register_wire_format",
    "unregister_wire_format",
]
