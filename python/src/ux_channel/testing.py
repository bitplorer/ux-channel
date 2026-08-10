"""Compatibility shim — implementation: ``ux_channel.host.testing``.

Stable::

    from ux_channel.testing import ...

Preferred::

    from ux_channel.host.testing import ...
"""
from __future__ import annotations

from ux_channel.host.testing import *  # noqa: F403

import ux_channel.host.testing as _impl

__all__ = [n for n in dir(_impl) if not n.startswith("_")]
