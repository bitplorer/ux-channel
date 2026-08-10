"""Compatibility shim — implementation: ``ux_channel.bridge_meta.bridge_contract``.

Stable::

    from ux_channel.bridge_contract import ...

Preferred::

    from ux_channel.bridge_meta.bridge_contract import ...
"""
from __future__ import annotations

from ux_channel.bridge_meta.bridge_contract import *  # noqa: F403

import ux_channel.bridge_meta.bridge_contract as _impl

__all__ = [n for n in dir(_impl) if not n.startswith("_")]
