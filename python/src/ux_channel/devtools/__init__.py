"""Devtools package — audit, inspect, CLI, observability.

Preferred::

    from ux_channel.devtools import attach_audit, inspect_channel
"""
from __future__ import annotations

from ux_channel.devtools.audit import AuditBundle, attach_audit
from ux_channel.devtools.inspect_api import inspect_channel, inspect_enabled

__all__ = [
    "attach_audit",
    "AuditBundle",
    "inspect_channel",
    "inspect_enabled"]
