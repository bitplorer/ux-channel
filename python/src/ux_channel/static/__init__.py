"""Static client assets shipped with the package (L5 tooling assets).

Design
    Browser JS (ux-channel client, webrtc, bridge helpers) rides with the wheel
    so apps do not re-host protocol clients by hand.

Architecture
    L5 static tree — not an implementation plane for Python IR.

Implementation
    Files live under this package directory; import is rarely needed in Python.
"""
from __future__ import annotations

__all__: list[str] = []
