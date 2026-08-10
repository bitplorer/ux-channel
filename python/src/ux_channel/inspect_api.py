"""Compatibility shim — implementation: ``ux_channel.ops_dx.inspect_api``.

Stable::

    from ux_channel.inspect_api import ...

Preferred::

    from ux_channel.ops_dx.inspect_api import ...
"""
from __future__ import annotations

from ux_channel.ops_dx.inspect_api import *  # noqa: F403

import ux_channel.ops_dx.inspect_api as _impl

__all__ = [n for n in dir(_impl) if not n.startswith("_")]
