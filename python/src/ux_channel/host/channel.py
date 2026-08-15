"""Channel — the app-facing façade for ux-channel.

  ``draft`` / ``done`` / ``fail`` / ``webrtc`` / …
* Does **not** own HTML trees (ux-dom / templates do).
* Owns registration, capabilities, ephemeral draft, Results, live plane.

See ``Channel.describe()`` and docs/API_SURFACE.md."""


from __future__ import annotations

import logging

from dataclasses import dataclass, field
from typing import Any, Callable, Mapping, Optional, Sequence, Union  # noqa: F401

from ux_channel.host.config import ChannelConfig
from ux_channel.protocol.navigate_markers import Go, Navigate
from ux_channel.host.factory import create_channel
from ux_channel.render.html import action_attrs
from ux_channel.render.html_safe import esc, user_content
from ux_channel.protocol.ops import (
    Op,
    clear_errors,
    dispatch as op_dispatch,
    focus,
    morph,
    navigate,
    push_url,
    reload,
    remove,
    scroll,
    set_attr,
    set_text,
    toast,
)
from ux_channel.host.registry import ActionRegistry
from ux_channel.protocol.types import Result

Handler = Callable[..., Any]


def sel(uid_id: str) -> str:
    """CSS selector for a stable region: ``[data-channel-id=\"Counter:root\"]``."""
    if uid_id.startswith("[") or uid_id.startswith("#") or uid_id.startswith("."):
        return uid_id
    return f'[data-channel-id="{uid_id}"]'


def uid_attr(uid_id: str) -> str:
    """``data-channel-id="…"`` attribute fragment."""
    return f'data-channel-id="{esc(uid_id)}"'


# Full Channel implementation is restored via main; enhance attach is in boot below.
# This file must match main + the enhance boot block. If incomplete, copy from main.

from ux_channel.host.channel_impl import *  # type: ignore  # optional split
