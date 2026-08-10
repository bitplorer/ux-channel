"""
Count-up / metric ticker bridge — animated numbers for dashboards.

    metrics = CountUpBridge(ch)
    mrr = metrics("mrr", value=12840, prefix="$", decimals=0, theme="emerald")
    return mrr.commit(value=14200)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ux_channel.bridges._factory import BridgeFactoryMixin

__all__ = ["CountUpBridge", "COUNTUP_PACKAGE", "COUNTUP_THEMES"]

COUNTUP_PACKAGE = "ux-fx/countup"
COUNTUP_METHODS = ("update", "destroy", "setValue", "replay")

COUNTUP_THEMES: dict[str, dict[str, str]] = {
    "emerald": {"color": "#34d399", "glow": "rgba(52, 211, 153, 0.35)"},
    "cyan": {"color": "#22d3ee", "glow": "rgba(34, 211, 238, 0.35)"},
    "violet": {"color": "#a78bfa", "glow": "rgba(167, 139, 250, 0.35)"},
    "rose": {"color": "#fb7185", "glow": "rgba(251, 113, 133, 0.35)"},
    "white": {"color": "#f8fafc", "glow": "rgba(248, 250, 252, 0.2)"},
}


@dataclass
class _State:
    value: float = 0.0
    duration_ms: int = 1200
    decimals: int = 0
    prefix: str = ""
    suffix: str = ""
    theme: str = "emerald"
    easing: str = "easeOutCubic"
    separator: bool = True


class CountUpBridge(BridgeFactoryMixin):
    package = COUNTUP_PACKAGE
    methods = COUNTUP_METHODS
    description = "Animated metric / count-up (ux-fx)"

    def __init__(
        self,
        ch: Any,
        id: str | None = None,
        *,
        value: float = 0.0,
        duration_ms: int = 1200,
        decimals: int = 0,
        prefix: str = "",
        suffix: str = "",
        theme: str = "emerald",
        easing: str = "easeOutCubic",
        separator: bool = True,
        auto_register: bool = True,
    ) -> None:
        super().__init__(
            ch,
            id,
            value=value,
            duration_ms=duration_ms,
            decimals=decimals,
            prefix=prefix,
            suffix=suffix,
            theme=theme,
            easing=easing,
            separator=separator,
            auto_register=auto_register,
        )

    def _new_state(self, **kwargs: Any) -> _State:
        return _State(**{k: v for k, v in kwargs.items() if k in _State.__dataclass_fields__})

    def _build_props(self) -> dict[str, Any]:
        st = self._state
        theme = COUNTUP_THEMES.get(st.theme, COUNTUP_THEMES["emerald"])
        return {
            "value": float(st.value),
            "durationMs": int(st.duration_ms),
            "decimals": int(st.decimals),
            "prefix": st.prefix,
            "suffix": st.suffix,
            "color": theme["color"],
            "glow": theme["glow"],
            "easing": st.easing,
            "separator": bool(st.separator),
            "theme": st.theme,
        }

    def set_value(self, value: float, **kwargs: Any) -> Any:
        self.configure(value=value, **kwargs)
        return self.fire("setValue", self.props())

    def replay(self) -> Any:
        return self.fire("replay")
