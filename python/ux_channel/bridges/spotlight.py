"""
Spotlight / glass-glow hover effect for premium card UIs.

    lights = SpotlightBridge(ch)
    card = lights("pricing", theme="violet", radius=280)
    return card.commit(theme="cyan")
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ux_channel.bridges._factory import BridgeFactoryMixin

__all__ = ["SpotlightBridge", "SPOTLIGHT_PACKAGE", "SPOTLIGHT_THEMES"]

SPOTLIGHT_PACKAGE = "ux-fx/spotlight"
SPOTLIGHT_METHODS = ("update", "destroy")

SPOTLIGHT_THEMES: dict[str, str] = {
    "violet": "rgba(167, 139, 250, 0.28)",
    "cyan": "rgba(34, 211, 238, 0.28)",
    "rose": "rgba(251, 113, 133, 0.28)",
    "gold": "rgba(251, 191, 36, 0.3)",
    "white": "rgba(255, 255, 255, 0.22)",
}


@dataclass
class _State:
    theme: str = "violet"
    radius: float = 260.0
    softness: float = 0.55
    border_glow: bool = True
    color: str = ""


class SpotlightBridge(BridgeFactoryMixin):
    package = SPOTLIGHT_PACKAGE
    methods = SPOTLIGHT_METHODS
    description = "Mouse spotlight glass glow (ux-fx)"

    def __init__(
        self,
        ch: Any,
        id: str | None = None,
        *,
        theme: str = "violet",
        radius: float = 260.0,
        softness: float = 0.55,
        border_glow: bool = True,
        color: str = "",
        auto_register: bool = True,
    ) -> None:
        super().__init__(
            ch,
            id,
            theme=theme,
            radius=radius,
            softness=softness,
            border_glow=border_glow,
            color=color,
            auto_register=auto_register,
        )

    def _new_state(self, **kwargs: Any) -> _State:
        return _State(**{k: v for k, v in kwargs.items() if k in _State.__dataclass_fields__})

    def _build_props(self) -> dict[str, Any]:
        st = self._state
        color = st.color or SPOTLIGHT_THEMES.get(st.theme, SPOTLIGHT_THEMES["violet"])
        return {
            "theme": st.theme,
            "color": color,
            "radius": float(st.radius),
            "softness": float(st.softness),
            "borderGlow": bool(st.border_glow),
        }
