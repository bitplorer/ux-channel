"""Compatibility shim — full alias of ``ux_channel.ops_dx.trace`` (stable 0.x import path).

All public and private attributes match the implementation module so
internal ``from ux_channel.trace import _helper`` keeps working.
"""
from __future__ import annotations

from importlib import import_module as _import_module
import sys as _sys

_impl = _import_module('ux_channel.ops_dx.trace')
_sys.modules[__name__] = _impl
