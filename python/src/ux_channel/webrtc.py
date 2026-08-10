"""Compatibility shim — implementation: ``ux_channel.realtime.webrtc``.

Stable::

    from ux_channel.webrtc import ...

Preferred::

    from ux_channel.realtime.webrtc import ...
"""
from __future__ import annotations

from ux_channel.realtime.webrtc import *  # noqa: F403

import ux_channel.realtime.webrtc as _impl

__all__ = [n for n in dir(_impl) if not n.startswith("_")]
