"""Protocol package — IR, ops, caps (Rust-parity shared law).

Design
    Owns the Intent → Result → ops vocabulary and CapService mint/verify.
    This is L1 peer core: dual-language forever; Python and Rust must agree
    with SPEC + conformance vectors.

Architecture
    App code may import types and builders here; transport (wire) and host
    (Channel) sit above. Caps travel *on* the Intent — not a separate auth plane.

Implementation
    ``types``, ``ops``, ``capability``, ``errors``; encode helpers live nearby.
    Preferred::

        from ux_channel.protocol import CapService, Intent, Result, morph, toast
"""
from __future__ import annotations

from ux_channel.protocol.capability import CapError, CapService
from ux_channel.protocol.errors import ActionError, ActionNotFound, ChannelError
from ux_channel.protocol.ops import (
    Op,
    clear_errors,
    focus,
    invoke,
    morph,
    navigate,
    noop,
    push_url,
    reload,
    remove,
    scroll,
    seq,
    set_attr,
    set_text,
    signal_set,
    swap,
    timer_clear,
    timer_set,
    toast,
)
from ux_channel.protocol.types import ErrorObject, Intent, Result
from ux_channel.protocol.navigate_markers import Go, Navigate

__all__ = [
    "CapService",
    "CapError",
    "Intent",
    "Result",
    "ErrorObject",
    "Op",
    "ChannelError",
    "ActionError",
    "ActionNotFound",
    "morph",
    "toast",
    "swap",
    "navigate",
    "reload",
    "focus",
    "scroll",
    "set_text",
    "set_attr",
    "remove",
    "clear_errors",
    "signal_set",
    "seq",
    "timer_set",
    "timer_clear",
    "invoke",
    "noop",
    "push_url",
    "Go",
    "Navigate",
]
