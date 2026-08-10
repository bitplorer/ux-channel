"""Tabs — switch panels via morph."""

from __future__ import annotations

from typing import Any, Mapping

from ux_channel.components.base import ChannelComponent
from ux_channel.render.html_safe import esc
from ux_channel.protocol.types import Result



def _button(host, label, action, **kwargs):
    """HTML button via host.button or region_button (Channel has no HTML façade)."""
    btn = getattr(host, "button", None)
    if callable(btn):
        return btn(label, action, **kwargs)
    from ux_channel.components.primitive import region_button
    reg = getattr(host, "registry", host)
    return region_button(reg, label, action, **kwargs)

class Tabs(ChannelComponent):
    """
    ::

        tabs = Tabs(ch, uid="Dash:tabs", panels={
            "overview": "<p>Overview</p>",
            "orders": "<p>Orders</p>",
        }).install()
        html = tabs.render(active="overview")
    """

    kind = "Tabs"

    def __init__(
        self,
        channel,
        *,
        uid: str | None = None,
        name: str = "Tabs",
        panels: Mapping[str, str] | None = None,
        labels: Mapping[str, str] | None = None,
    ):
        super().__init__(channel, uid=uid, name=name)
        self.panels = dict(panels or {})
        self.labels = dict(labels or {})

    def render(self, **state: Any) -> str:
        keys = list(self.panels.keys())
        active = str(state.get("active") or (keys[0] if keys else ""))
        if active not in self.panels and keys:
            active = keys[0]
        tab_btns = []
        for k in keys:
            label = self.labels.get(k, k.title())
            cls = "ux-tab ux-tab-active" if k == active else "ux-tab"
            style = (
                "padding:.4rem .75rem;border:none;border-bottom:2px solid "
                + ("#2563eb" if k == active else "transparent")
                + ";background:transparent;cursor:pointer"
            )
            tab_btns.append(
                _button(self.ch, 
                    label,
                    self.action_name("select"),
                    args={"active": k},
                    target=self.uid,
                    class_name=cls,
                    style=style,
                )
            )
        panel = self.panels.get(active, "")
        return self.wrap(
            f'<div class="ux-tabs-bar" style="display:flex;gap:.25rem;border-bottom:1px solid #e2e8f0;margin-bottom:.75rem">'
            f'{"".join(tab_btns)}</div>'
            f'<div class="ux-tabs-panel">{panel}</div>',
            class_="ux-tabs",
        )

    def _register(self) -> None:
        comp = self

        @self.ch.action(self.action_name("select"))
        def select(active: str = "") -> Result:
            return comp.refresh(active=active)
