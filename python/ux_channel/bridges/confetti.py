"""
Confetti effect bridge — celebration bursts without writing canvas code.

    confetti = ConfettiBridge(ch)
    win = confetti("win", particle_count=120, theme="gold")
    return win.burst()                 # Result with bridge.call("burst")
    # host: Div(**win.mount_spec(class_name="pointer-events-none fixed inset-0").attrs_py)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Sequence

from ux_channel.bridges._factory import BridgeFactoryMixin

__all__ = ["ConfettiBridge", "CONFETTI_PACKAGE", "CONFETTI_THEMES"]

CONFETTI_PACKAGE = "ux-fx/confetti"
CONFETTI_METHODS = ("update", "destroy", "burst", "cannon", "rain", "stop")

CONFETTI_THEMES: dict[str, list[str]] = {
    "gold": ["#fbbf24", "#f59e0b", "#fde68a", "#ffffff"],
    "neon": ["#22d3ee", "#a78bfa", "#f472b6", "#34d399"],
    "rose": ["#fb7185", "#fda4af", "#fecdd3", "#fff1f2"],
    "ocean": ["#38bdf8", "#0ea5e9", "#67e8f9", "#e0f2fe"],
    "pride": ["#ef4444", "#f97316", "#eab308", "#22c55e", "#3b82f6", "#8b5cf6"],
    "mono": ["#f8fafc", "#cbd5e1", "#94a3b8", "#64748b"],
}


@dataclass
class _State:
    particle_count: int = 100
    spread: float = 70.0
    start_velocity: float = 45.0
    gravity: float = 1.0
    scalar: float = 1.0
    theme: str = "neon"
    colors: list[str] = field(default_factory=list)
    origin_x: float = 0.5
    origin_y: float = 0.5
    ticks: int = 200
    z_index: int = 9999


class ConfettiBridge(BridgeFactoryMixin):
    package = CONFETTI_PACKAGE
    methods = CONFETTI_METHODS
    description = "Canvas confetti bursts (ux-fx)"

    def __init__(
        self,
        ch: Any,
        id: str | None = None,
        *,
        particle_count: int = 100,
        spread: float = 70.0,
        start_velocity: float = 45.0,
        gravity: float = 1.0,
        scalar: float = 1.0,
        theme: str = "neon",
        colors: Sequence[str] | None = None,
        origin_x: float = 0.5,
        origin_y: float = 0.5,
        ticks: int = 200,
        z_index: int = 9999,
        auto_register: bool = True,
    ) -> None:
        super().__init__(
            ch,
            id,
            particle_count=particle_count,
            spread=spread,
            start_velocity=start_velocity,
            gravity=gravity,
            scalar=scalar,
            theme=theme,
            colors=list(colors or []),
            origin_x=origin_x,
            origin_y=origin_y,
            ticks=ticks,
            z_index=z_index,
            auto_register=auto_register,
        )

    def _new_state(self, **kwargs: Any) -> _State:
        return _State(**{k: v for k, v in kwargs.items() if k in _State.__dataclass_fields__})

    def _build_props(self) -> dict[str, Any]:
        st = self._state
        colors = list(st.colors) or list(CONFETTI_THEMES.get(st.theme, CONFETTI_THEMES["neon"]))
        return {
            "particleCount": int(st.particle_count),
            "spread": float(st.spread),
            "startVelocity": float(st.start_velocity),
            "gravity": float(st.gravity),
            "scalar": float(st.scalar),
            "colors": colors,
            "origin": {"x": float(st.origin_x), "y": float(st.origin_y)},
            "ticks": int(st.ticks),
            "zIndex": int(st.z_index),
            "theme": st.theme,
        }

    def burst(self, **overrides: Any) -> Any:
        """Celebrate once (default method for wins)."""
        if overrides:
            self.configure(**overrides)
        return self.fire("burst", self.props())

    def cannon(self, **overrides: Any) -> Any:
        if overrides:
            self.configure(**overrides)
        return self.fire("cannon", self.props())

    def rain(self, duration_ms: int = 2500, **overrides: Any) -> Any:
        if overrides:
            self.configure(**overrides)
        props = self.props()
        props["durationMs"] = int(duration_ms)
        return self.fire("rain", props)

    def stop(self) -> Any:
        return self.fire("stop")
