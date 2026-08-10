"""Cohesive package: **devtools**

Audit, CLI, observability, dashboards, agents façade.

Modules: agent_peer, agents_api, audit, cli, codegen, dashboard, enterprise, errors, explain, forensics, info, inspect_api, intent_log, log, metrics_prom, observability, otel, profiling, pydantic_actions, schema_models, ticket_revoke, trace, upgrade_check

Import: ``from ux_channel.devtools.MODULE import Symbol``
Public apps: ``from ux_channel.api import …`` or ``from ux_channel import …``

Source of truth: PACKAGE_MAP.json
"""
from __future__ import annotations

MEMBERS = ['agent_peer', 'agents_api', 'audit', 'cli', 'codegen', 'dashboard', 'enterprise', 'errors', 'explain', 'forensics', 'info', 'inspect_api', 'intent_log', 'log', 'metrics_prom', 'observability', 'otel', 'profiling', 'pydantic_actions', 'schema_models', 'ticket_revoke', 'trace', 'upgrade_check']
PACKAGE = 'devtools'
__all__ = ["MEMBERS", "PACKAGE"]
