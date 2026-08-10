"""Compatibility shim — implementation: ``ux_channel.ops_dx.schema_models``.

Stable::

    from ux_channel.schema_models import ...

Preferred::

    from ux_channel.ops_dx.schema_models import ...
"""
from __future__ import annotations

from ux_channel.ops_dx.schema_models import *  # noqa: F403

import ux_channel.ops_dx.schema_models as _impl

__all__ = [n for n in dir(_impl) if not n.startswith("_")]
