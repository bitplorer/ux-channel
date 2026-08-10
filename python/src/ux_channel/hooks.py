"""Compatibility shim — implementation: ``ux_channel.host.hooks``.

Stable::

    from ux_channel.hooks import ...

Preferred::

    from ux_channel.host.hooks import ...
"""
from __future__ import annotations

from ux_channel.host.hooks import *  # noqa: F403

import ux_channel.host.hooks as _impl

__all__ = [n for n in dir(_impl) if not n.startswith("_")]
