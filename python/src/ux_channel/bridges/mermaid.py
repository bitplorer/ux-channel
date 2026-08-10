
"""Mermaid diagram bridge — architecture & flow diagrams in ux-dom."""

from __future__ import annotations
from dataclasses import dataclass
from typing import Any
from ux_channel.bridges._factory import BridgeFactoryMixin

__all__ = ["MermaidBridge", "MERMAID_PACKAGE"]
MERMAID_PACKAGE = "mermaid"
MERMAID_METHODS = ("update", "destroy", "render")

@dataclass
class _State:
    chart: str = "graph TD\n  A-->B"
    theme: str = "dark"
    security_level: str = "strict"

class MermaidBridge(BridgeFactoryMixin):
    package = MERMAID_PACKAGE
    methods = MERMAID_METHODS
    description = "Mermaid diagrams"

    def __init__(self, ch, id=None, *, chart="graph TD\n  A-->B", theme="dark",
                 security_level="strict", auto_register=True):
        super().__init__(
            ch, id, chart=chart, theme=theme, security_level=security_level,
            auto_register=auto_register,
        )

    def _new_state(self, **kw):
        return _State(**{k: v for k, v in kw.items() if k in _State.__dataclass_fields__})

    def _build_props(self):
        st = self._state
        return {
            "chart": st.chart,
            "theme": st.theme,
            "securityLevel": st.security_level,
        }

    def render(self, chart: str | None = None):
        if chart is not None:
            self.configure(chart=chart)
        return self.fire("render", self.props())
