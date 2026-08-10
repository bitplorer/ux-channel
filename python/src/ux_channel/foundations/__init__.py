"""Foundations package — quantity, provenance, io_channel.

Preferred::

    from ux_channel.foundations import Quantity
"""
from __future__ import annotations

# MANUAL_PUBLIC_API — sync_python_layout must not overwrite this file

from ux_channel.foundations.quantity import Quantity

PACKAGE = "foundations"
__all__ = ["PACKAGE", "Quantity"]
