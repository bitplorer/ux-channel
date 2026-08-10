"""
Particle field bridge — ambient interactive particles for hero UIs.

    field = ParticlesBridge(ch)
    hero = field("hero", count=60, theme="aurora", interactive=True)
    return hero.commit(count=80)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ux_channel.bridges._factory import BridgeFactoryMixin

__all__ = ["ParticlesBridge", "PARTICLES_PACKAGE", "PARTICLE_THEMES"]

PARTICLES_PACKAGE = "ux-fx/particles"
PARTICLES_METHODS = ("update", "destroy", "pulse", "burst")

PARTICLE_THEMES: dict[str, dict[str, Any]] = {
    "aurora": {
        "colors": ["#22d3ee", "#a78bfa", "#34d399", "#f472b6"],
        "bg": "transparent",
        "link": "rgba(167, 139, 250, 0.18)",
    },
    "ember": {
        "colors": ["#f97316", "#ef4444", "#fbbf24", "#fb7185"],
        "bg": "transparent",
        "link": "rgba(249, 115, 22, 0.2)",
    },
    "ocean": {
        "colors": ["#0ea5e9", "#06b6d4", "#38bdf8", "#e0f2fe"],
        "bg": "transparent",
        "link": "rgba(14, 165, 233, 0.2)",
    },
    "mono": {
        "colors": ["#f8fafc", "#94a3b8", "#64748b"],
        "bg": "transparent",
        "link": "rgba(148, 163, 184, 0.15)",
    },
}


@dataclass
class _State:
    count: int = 55
    theme: str = "aurora"
    speed: float = 0.45
    size: float = 2.2
    link_distance: float = 120.0
    interactive: bool = True
    opacity: float = 0.85


class ParticlesBridge(BridgeFactoryMixin):
    package = PARTICLES_PACKAGE
    methods = PARTICLES_METHODS
    description = "Ambient particle field (ux-fx)"

    def __init__(
        self,
        ch: Any,
        id: str | None = None,
        *,
        count: int = 55,
        theme: str = "aurora",
        speed: float = 0.45,
        size: float = 2.2,
        link_distance: float = 120.0,
        interactive: bool = True,
        opacity: float = 0.85,
        auto_register: bool = True,
    ) -> None:
        super().__init__(
            ch,
            id,
            count=count,
            theme=theme,
            speed=speed,
            size=size,
            link_distance=link_distance,
            interactive=interactive,
            opacity=opacity,
            auto_register=auto_register,
        )

    def _new_state(self, **kwargs: Any) -> _State:
        return _State(**{k: v for k, v in kwargs.items() if k in _State.__dataclass_fields__})

    def _build_props(self) -> dict[str, Any]:
        st = self._state
        theme = PARTICLE_THEMES.get(st.theme, PARTICLE_THEMES["aurora"])
        return {
            "count": int(st.count),
            "colors": list(theme["colors"]),
            "bg": theme["bg"],
            "linkColor": theme["link"],
            "speed": float(st.speed),
            "size": float(st.size),
            "linkDistance": float(st.link_distance),
            "interactive": bool(st.interactive),
            "opacity": float(st.opacity),
            "theme": st.theme,
        }

    def pulse(self) -> Any:
        return self.fire("pulse")

    def burst(self, x: float = 0.5, y: float = 0.5) -> Any:
        return self.fire("burst", {"x": x, "y": y})
