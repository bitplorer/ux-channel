"""Compatibility shim — implementation: ``ux_channel.ops_dx.ticket_revoke``.

Stable::

    from ux_channel.ticket_revoke import ...

Preferred::

    from ux_channel.ops_dx.ticket_revoke import ...
"""
from __future__ import annotations

from ux_channel.ops_dx.ticket_revoke import *  # noqa: F403

import ux_channel.ops_dx.ticket_revoke as _impl

__all__ = [n for n in dir(_impl) if not n.startswith("_")]
