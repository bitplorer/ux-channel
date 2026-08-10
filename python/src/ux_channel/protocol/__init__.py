"""Protocol package — IR, ops, caps (Rust-parity shared law).

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
    morph,
    navigate,
    noop,
    push_url,
    reload,
    remove,
    scroll,
    set_attr,
    set_text,
    signal_set,
    swap,
    toast,
)
from ux_channel.protocol.types import ErrorObject, Intent, Result
from ux_channel.protocol.encode import Go, Navigate

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
    "noop",
    "push_url",
    "Go",
    "Navigate"]
