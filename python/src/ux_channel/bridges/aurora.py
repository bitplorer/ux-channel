"""
Aurora / mesh-gradient background bridge — cinematic full-bleed motion.

    skies = AuroraBridge(ch)
    hero = skies("bg", theme="midnight", intensity=0.9)
    return hero.commit(theme="sunset")
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Sequence

from ux_channel.bridges._factory import BridgeFactoryMixin

__all__ = ["AuroraBridge", "AURORA_PACKAGE", "AURORA_THEMES"]

AURORA_PACKAGE = "ux-fx/aurora"
AURORA_METHODS = ("update", "destroy", "pause", "play")

AURORA_THEMES: dict[str, list[str]] = {
    "midnight": ["#0f172a", "#312e81", "#4c1d95", "#0e7490", "#1e1b4b"],
    "sunset": ["#7c2d12", "#9f1239", "#c2410c", "#a21caf", "#1c1917"],
    "forest": ["#052e16", "#14532d", "#0f766e", "#365314", "#022c22"],
    "candy": ["#4c1d95", "#db2777", "#7c3aed", "#06b6d4", "#1e1b4b"],
    "noir": ["#09090b", "#18181b", "#27272a", "#3f3f46", "#000000"],
}


@dataclass
class _State:
    theme: str = "midnight"
    intensity: float = 0.85
    speed: float = 0.35
    blur: float = 48.0
    blobs: int = 5
    colors: list[str] | None = None
    reduce_motion: bool = False


class AuroraBridge(BridgeFactoryMixin):
    package = AURORA_PACKAGE
    methods = AURORA_METHODS
    description = "Animated aurora / mesh gradient (ux-fx)"

    def __init__(
        self,
        ch: Any,
        id: str | None = None,
        *,
        theme: str = "midnight",
        intensity: float = 0.85,
        speed: float = 0.35,
        blur: float = 48.0,
        blobs: int = 5,
        colors: Sequence[str] | None = None,
        reduce_motion: bool = False,
        auto_register: bool = True,
    ) -> None:
        super().__init__(
            ch,
            id,
            theme=theme,
            intensity=intensity,
            speed=speed,
            blur=blur,
            blobs=blobs,
            colors=list(colors) if colors is not None else None,
            reduce_motion=reduce_motion,
            auto_register=auto_register,
        )

    def _new_state(self, **kwargs: Any) -> _State:
        return _State(**{k: v for k, v in kwargs.items() if k in _State.__dataclass_fields__})

    def _build_props(self) -> dict[str, Any]:
        st = self._state
        colors = list(st.colors) if st.colors else list(
            AURORA_THEMES.get(st.theme, AURORA_THEMES["midnight"])
        )
        return {
            "theme": st.theme,
            "colors": colors,
            "intensity": float(st.intensity),
            "speed": float(st.speed),
            "blur": float(st.blur),
            "blobs": int(st.blobs),
            "reduceMotion": bool(st.reduce_motion),
        }

    def pause(self) -> Any:
        return self.fire("pause")

    def play(self) -> Any:
        return self.fire("play")
