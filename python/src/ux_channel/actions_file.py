"""Compatibility shim — implementation: ``ux_channel.host.actions_file``.

Stable::

    from ux_channel.actions_file import ...

Preferred::

    from ux_channel.host.actions_file import ...
"""
from __future__ import annotations

from ux_channel.host.actions_file import *  # noqa: F403

import ux_channel.host.actions_file as _impl

__all__ = [n for n in dir(_impl) if not n.startswith("_")]
