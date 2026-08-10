"""Compatibility shim — implementation: ``ux_channel.foundations.provenance``.

Stable::

    from ux_channel.provenance import ...

Preferred::

    from ux_channel.foundations.provenance import ...
"""
from __future__ import annotations

from ux_channel.foundations.provenance import *  # noqa: F403

import ux_channel.foundations.provenance as _impl

__all__ = [n for n in dir(_impl) if not n.startswith("_")]
