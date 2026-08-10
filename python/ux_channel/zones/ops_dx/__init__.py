"""Zone: **ops_dx**

Audit, CLI, observability — **operate and diagnose**.

This package does **not** move implementations. It is a **navigation + re-export hub**
so you never have to guess intent from a flat 100-file directory listing.

Canonical implementations still live at ``ux_channel.<module>`` (stable import paths).
Prefer day-1: ``from ux_channel.day1 import ...``.

Members
-------
* ``audit`` — attach_audit intent log+forensics
* ``intent_log`` — Ordered Intent log
* ``forensics`` — Reconstruct painted frames
* ``trace`` — Action/bridge tracing
* ``explain`` — Teachable error recipes
* ``inspect_api`` — Live inspect (prod-closed)
* ``observability`` — Logging/metrics hooks
* ``otel`` — OpenTelemetry (optional)
* ``metrics_prom`` — Prometheus sink (optional)
* ``profiling`` — Maintainer profiling
* ``dx_errors`` — CLI/DX exceptions
* ``dx_log`` — DX console logging
* ``dx_dashboard`` — Operator dashboard
* ``info`` — Package/runtime info
* ``upgrade_check`` — Scan projects for outdated patterns
* ``cli`` — uxchannel CLI
* ``__main__`` — python -m ux_channel
* ``_version`` — Package version
* ``codegen`` — TS client codegen (optional)
* ``enterprise`` — Multi-tenant helpers
* ``pydantic_actions`` — Pydantic-validated actions (opt)
* ``schema_models`` — Optional Pydantic IR models
* ``ticket_revoke`` — Revoke live push tickets
* ``scaffold`` — SUBPACKAGE: project scaffold templates
"""
from __future__ import annotations

ZONE = "ops_dx"
DESCRIPTION = 'Audit, CLI, observability — **operate and diagnose**.'

MEMBERS: dict[str, str] = {
    'audit': 'attach_audit intent log+forensics',
    'intent_log': 'Ordered Intent log',
    'forensics': 'Reconstruct painted frames',
    'trace': 'Action/bridge tracing',
    'explain': 'Teachable error recipes',
    'inspect_api': 'Live inspect (prod-closed)',
    'observability': 'Logging/metrics hooks',
    'otel': 'OpenTelemetry (optional)',
    'metrics_prom': 'Prometheus sink (optional)',
    'profiling': 'Maintainer profiling',
    'dx_errors': 'CLI/DX exceptions',
    'dx_log': 'DX console logging',
    'dx_dashboard': 'Operator dashboard',
    'info': 'Package/runtime info',
    'upgrade_check': 'Scan projects for outdated patterns',
    'cli': 'uxchannel CLI',
    '__main__': 'python -m ux_channel',
    '_version': 'Package version',
    'codegen': 'TS client codegen (optional)',
    'enterprise': 'Multi-tenant helpers',
    'pydantic_actions': 'Pydantic-validated actions (opt)',
    'schema_models': 'Optional Pydantic IR models',
    'ticket_revoke': 'Revoke live push tickets',
    'scaffold': 'SUBPACKAGE: project scaffold templates',
}

__all__ = ["ZONE", "DESCRIPTION", "MEMBERS", "help"]

def help() -> str:
    """Human summary of this zone."""
    rows = "\n".join(f"  {k:24} {v}" for k, v in MEMBERS.items())
    return f"zone={ZONE}\n{DESCRIPTION}\n\n{rows}\n"

