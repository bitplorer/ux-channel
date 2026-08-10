"""Zone / package: **ops_dx**

Audit, CLI, observability, agents façade.

Physical code: ``ux_channel.{pkg}`` (or existing subpackage).
"""
from __future__ import annotations
ZONE = 'ops_dx'
DESCRIPTION = 'Audit, CLI, observability, agents façade.'
MEMBERS = {'agent_peer': 'Agent peer Intent path — internal to AX (``agents_api``).', 'agents_api': 'AX — Agent Experience façade (day-1 public).', 'audit': 'Audit — intent log + forensics as one attach.', 'cli': 'uxchannel CLI super-command for **ux-channel**.', 'codegen': 'Minimal TypeScript client codegen from ActionRegistry (optional power).', 'dx_dashboard': 'DX Dashboard — observe-only operator surface for **ux-channel**.', 'dx_errors': 'DX / CLI exceptions — cognitively consistent, never silent failures.', 'dx_log': 'DX console logging — nothing silent; text or structured JSON for automation.', 'enterprise': 'Enterprise helpers — multi-tenant safety nets for production apps.', 'explain': 'Teachable failures — map error codes / results to recipes and fixes.', 'forensics': 'Forensic frames — reconstruct what was painted after an Intent.', 'info': 'Package / runtime info for /version endpoints and diagnostics.', 'inspect_api': 'Live UX · AX · DX inspect — read-only, principal-scoped, prod-closed by default.', 'intent_log': 'Intent log — ordered record of dispatched Intents (support / audit).', 'metrics_prom': 'Prometheus metrics sink (optional).', 'observability': 'Logging and metrics hooks for production observability.', 'otel': 'OpenTelemetry integration for **ux-channel** (optional soft dependency).', 'profiling': 'Internal / maintainer profiling helpers (not a day-1 user API).', 'pydantic_actions': 'Pydantic-validated actions (optional; requires pydantic v2).', 'schema_models': 'Optional Pydantic models for OpenAPI / typed Intent-Result (extra: pydantic).', 'ticket_revoke': 'Ticket revocation — logout / ban kills live push tickets.', 'trace': 'Action & bridge tracing — Wireshark-like DX for the Channel protocol.', 'upgrade_check': 'Scan a project tree for outdated / high-cognitive-load patterns.'}
__all__ = ["ZONE", "DESCRIPTION", "MEMBERS", "help"]

def help() -> str:
    rows = "\n".join(f"  {k:28} {v}" for k, v in MEMBERS.items())
    return f"zone={ZONE}\n{DESCRIPTION}\n\n{rows}\n"
