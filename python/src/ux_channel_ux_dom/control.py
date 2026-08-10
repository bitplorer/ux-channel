"""Wire channel controls to ux-dom kwargs (data_channel_*)."""

from __future__ import annotations

from typing import Any, Mapping, Optional

from ux_channel.paint.html import ControlAttrs


def control_ux_dom(channel: Any, action: Any, **trust: Any) -> dict[str, str]:
    """``button(..., **control_ux_dom(ch, pay, trust_order_id=oid))``."""
    return channel.control(action, **trust).as_ux_dom()


def bind_action(channel: Any, action: Any, **trust: Any) -> dict[str, str]:
    """Alias of control_ux_dom for st-like speech."""
    return control_ux_dom(channel, action, **trust)


def control_attrs(channel: Any, action: Any, **trust: Any) -> ControlAttrs:
    return channel.control(action, **trust)
