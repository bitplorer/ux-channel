"""Compatibility shim — implementation: ``ux_channel.paint.html_document``.

Stable: ``from ux_channel.html_document import ...``
Preferred package path: ``ux_channel.paint.html_document``
"""
from __future__ import annotations

from ux_channel.paint.html_document import *  # noqa: F403
import ux_channel.paint.html_document as _impl

__all__ = list(getattr(_impl, "__all__", [n for n in dir(_impl) if not n.startswith("_")]))
