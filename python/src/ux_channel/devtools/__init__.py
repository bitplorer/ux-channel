"""Devtools package — audit, inspect, CLI, observability.

Preferred::

    from ux_channel.devtools import attach_audit, inspect_channel
"""
from __future__ import annotations

# MANUAL_PUBLIC_API — sync_python_layout must not overwrite this file

from ux_channel.devtools.audit import AuditBundle, attach_audit
from ux_channel.devtools.inspect_api import inspect_channel, inspect_enabled

PACKAGE = "devtools"
__all__ = [
    "PACKAGE",
    "attach_audit",
    "AuditBundle",
    "inspect_channel",
    "inspect_enabled",
]
