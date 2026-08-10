
"""Leaflet map bridge — high-value for location UIs (ux-dom host)."""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Sequence
from ux_channel.bridges._factory import BridgeFactoryMixin

__all__ = ["LeafletBridge", "LEAFLET_PACKAGE"]
LEAFLET_PACKAGE = "leaflet"
LEAFLET_METHODS = ("update", "destroy", "setView", "flyTo", "invalidateSize")

@dataclass
class _State:
    center: list[float] = field(default_factory=lambda: [20.0, 0.0])
    zoom: int = 2
    tiles: str = "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
    attribution: str = "&copy; OpenStreetMap"
    markers: list[dict] = field(default_factory=list)
    fit_markers: bool = False

class LeafletBridge(BridgeFactoryMixin):
    package = LEAFLET_PACKAGE
    methods = LEAFLET_METHODS
    description = "Leaflet map"

    def __init__(self, ch, id=None, *, center=None, zoom=2, tiles=None,
                 attribution=None, markers=None, fit_markers=False, auto_register=True):
        super().__init__(
            ch, id,
            center=list(center or [20.0, 0.0]),
            zoom=zoom,
            tiles=tiles or "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png",
            attribution=attribution or "&copy; OpenStreetMap",
            markers=list(markers or []),
            fit_markers=fit_markers,
            auto_register=auto_register,
        )

    def _new_state(self, **kw):
        return _State(**{k: v for k, v in kw.items() if k in _State.__dataclass_fields__})

    def _build_props(self):
        st = self._state
        return {
            "center": list(st.center),
            "zoom": int(st.zoom),
            "tiles": st.tiles,
            "attribution": st.attribution,
            "markers": list(st.markers),
            "fitMarkers": bool(st.fit_markers),
        }

    def set_view(self, center, zoom=None):
        self.configure(center=list(center), **({"zoom": zoom} if zoom is not None else {}))
        args = [list(center)]
        if zoom is not None:
            args.append(zoom)
        return self.fire("setView", *args)

    def fly_to(self, center, zoom=None):
        args = [list(center)]
        if zoom is not None:
            args.append(zoom)
        return self.fire("flyTo", *args)
