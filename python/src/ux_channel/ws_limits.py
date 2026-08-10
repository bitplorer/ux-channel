"""Compatibility shim — implementation: ``ux_channel.transport.ws_limits``.

Stable::

    from ux_channel.ws_limits import ...

Preferred::

    from ux_channel.transport.ws_limits import ...
"""
from __future__ import annotations

from ux_channel.transport.ws_limits import *  # noqa: F403

import ux_channel.transport.ws_limits as _impl

__all__ = [n for n in dir(_impl) if not n.startswith("_")]
