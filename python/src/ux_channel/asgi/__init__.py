"""ASGI adapters — FastAPI / Starlette host mounting (L3).

Design
    Transport door for HTTP: mount a Channel onto an ASGI app without putting
    framework types into host core.

Architecture
    L3 adapter — stable *contracts* (mount + action path), swappable framework
    helpers. Does not define IR or caps.

Implementation
    ``fastapi.mount_channel`` is the preferred entry; Starlette helpers optional.
    Preferred::

        from ux_channel.asgi import mount_channel
        from ux_channel.asgi.enhance_routes import mount_enhance_routes
"""
from __future__ import annotations

__all__: list[str] = []

try:
    from ux_channel.asgi.fastapi import mount_channel

    __all__.append("mount_channel")
except Exception:  # pragma: no cover
    pass

try:
    from ux_channel.asgi.enhance_routes import mount_enhance_routes, project_result_for_request

    __all__.extend(["mount_enhance_routes", "project_result_for_request"])
except Exception:  # pragma: no cover
    pass
