"""Compatibility shim — implementation: ``ux_channel.realtime.webrtc_metrics``.

Stable::

    from ux_channel.webrtc_metrics import ...

Preferred::

    from ux_channel.realtime.webrtc_metrics import ...
"""
from __future__ import annotations

from ux_channel.realtime.webrtc_metrics import *  # noqa: F403

import ux_channel.realtime.webrtc_metrics as _impl

__all__ = [n for n in dir(_impl) if not n.startswith("_")]
