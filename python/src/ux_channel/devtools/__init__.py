"""Devtools package — audit, inspect, CLI, observability (L5 tooling).

Design
    Free-to-churn operator surface. Must not become required for production
    dispatch or pollute the application root exports.

Architecture
    L5 only — hangs off Channel via attach hooks; identity of CapService/Channel
    stays in protocol/host.

Implementation
    Audit bundle + inspect API are the stable-ish entry; dashboard/CLI may churn.
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
