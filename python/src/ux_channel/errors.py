"""
Channel error types — **public**.

Raise ``ActionError`` from handlers to produce ``ok=false`` Results.
``WebRTCError`` is for the signaling plane only.
"""

from __future__ import annotations

from typing import Any, Mapping, Optional, Sequence

__all__ = ["ChannelError", "ActionNotFound", "ActionError", "WebRTCError"]


class ChannelError(Exception):
    """Base error for uxchannel (public)."""


class ActionNotFound(ChannelError):
    """Unknown action name on the registry (public)."""

    def __init__(self, name: str):
        self.name = name
        super().__init__(f"unknown action: {name}")


class ActionError(ChannelError):
    """
    Raise from an action to produce ok=false Result (public).

    Example::

        raise ActionError("validation", "Invalid email", fields={"email": ["required"]})
    """

    def __init__(
        self,
        code: str,
        message: str,
        *ops: Mapping[str, Any],
        fields: Optional[dict[str, list[str]]] = None,
        ops_list: Optional[Sequence[Mapping[str, Any]]] = None,
        retryable: bool = False,
        details: Any = None,
    ):
        self.code = code
        self.message = message
        self.fields = fields
        self.retryable = retryable
        self.details = details
        if ops_list is not None:
            self.ops = [dict(o) for o in ops_list]
        else:
            self.ops = [dict(o) for o in ops]
        super().__init__(message)


class WebRTCError(ChannelError):
    """Signaling / room / ticket failure on the WebRTC plane (public)."""

    def __init__(self, code: str, message: str):
        self.code = code
        self.message = message
        super().__init__(f"{code}: {message}")
