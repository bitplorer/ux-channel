"""Compatibility shim — implementation: ``ux_channel.paint.html``.

Stable: ``from ux_channel.html import ...``
Preferred package path: ``ux_channel.paint.html``
"""
from __future__ import annotations

from ux_channel.paint.html import *  # noqa: F403
import ux_channel.paint.html as _impl

__all__ = list(getattr(_impl, "__all__", [n for n in dir(_impl) if not n.startswith("_")]))
