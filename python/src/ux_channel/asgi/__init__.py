"""ASGI adapters — FastAPI / Starlette host mounting.

::

    from ux_channel.asgi import mount_channel
"""
from __future__ import annotations

__all__: list[str] = []

try:
    from ux_channel.asgi.fastapi import mount_channel

    __all__.append("mount_channel")
except Exception:  # pragma: no cover
    pass
