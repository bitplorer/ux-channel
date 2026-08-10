"""
Plug-and-play app scaffolding for ux-channel.

Public API
----------
* :func:`create_app` — write a project tree with safe defaults
* :func:`available_templates` — ``minimal`` | ``live`` | ``webrtc`` | ``full``
* :func:`validate_scaffold` — post-create integrity checks

CLI::

    uxchannel create-app myapp
    uxchannel create-app myapp --template webrtc
    uxchannel create-app myapp --template full --uxdom Design goals (low cognitive load)
---------------------------------
1. **One default path that works** — development config, memory stores, no Redis.
2. **Named templates** — pick a shape; do not assemble flags by hand.
3. **Comments in generated code** — every file explains *why*, not only *what*.
4. **Channel owns control; your HTML owns layout** — scaffold never
   invents a second UI framework.
"""
from __future__ import annotations

from ux_channel.scaffold.create import (
    ScaffoldOptions,
    available_templates,
    create_app,
    validate_scaffold,
)

__all__ = [
    "ScaffoldOptions",
    "available_templates",
    "create_app",
    "validate_scaffold"]
