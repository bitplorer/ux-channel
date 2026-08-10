"""Compatibility shim — implementation: ``ux_channel.paint.html_safe``.

Stable::

    from ux_channel.html_safe import ...

Preferred::

    from ux_channel.paint.html_safe import ...
"""
from __future__ import annotations

from ux_channel.paint.html_safe import *  # noqa: F403

import ux_channel.paint.html_safe as _impl

__all__ = [n for n in dir(_impl) if not n.startswith("_")]
