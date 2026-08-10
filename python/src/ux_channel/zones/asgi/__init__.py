"""Zone / package: **asgi**

SUBPACKAGE: HTTP/ASGI adapters.

Physical code: ``ux_channel.{pkg}`` (or existing subpackage).
"""
from __future__ import annotations
ZONE = 'asgi'
DESCRIPTION = 'SUBPACKAGE: HTTP/ASGI adapters.'
MEMBERS = {'core': 'Pure ASGI Channel endpoint — framework-agnostic host core.', 'fastapi': 'FastAPI host adapter — production-capable Channel HTTP surface.', 'pipeline': 'Shared HTTP preflight for POST /action — one policy for FastAPI + Starlette.', 'starlette': 'Starlette host adapter — security parity with FastAPI (next steps).'}
__all__ = ["ZONE", "DESCRIPTION", "MEMBERS", "help"]

def help() -> str:
    rows = "\n".join(f"  {k:28} {v}" for k, v in MEMBERS.items())
    return f"zone={ZONE}\n{DESCRIPTION}\n\n{rows}\n"
