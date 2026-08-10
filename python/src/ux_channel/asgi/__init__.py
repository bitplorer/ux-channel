"""ASGI adapters — FastAPI / Starlette host mounting.

Preferred::

    from ux_channel.asgi import mount_channel
    # or: from ux_channel.asgi.fastapi import mount_channel
"""
from __future__ import annotations

PACKAGE = "asgi"
__all__ = ["PACKAGE"]

try:
    from ux_channel.asgi.fastapi import mount_channel

    __all__ += ["mount_channel"]
except Exception:  # pragma: no cover - optional heavy import
    pass
