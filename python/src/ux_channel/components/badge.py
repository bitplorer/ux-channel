"""Badge — simple count/status pill that morphs in place."""

from __future__ import annotations

from typing import Any

from ux_channel.components.base import ChannelComponent
from ux_channel.render.html_safe import esc
from ux_channel.protocol.types import Result


class Badge(ChannelComponent):
    """
    ::

        badge = Badge(ch, uid="Cart:badge", label="Cart").install()
        return badge.set(3)
    """

    kind = "Badge"

    def __init__(self, channel, *, uid: str | None = None, name: str = "Badge", label: str = ""):
        super().__init__(channel, uid=uid, name=name)
        self.label = label

    def render(self, **state: Any) -> str:
        count = state.get("count", 0)
        label = state.get("label", self.label)
        text = f"{label} {count}".strip() if label else str(count)
        return self.wrap(
            f'<span class="ux-badge-pill" style="display:inline-flex;align-items:center;'
            f'background:#0f172a;color:#fff;border-radius:999px;padding:.15rem .6rem;'
            f'font-size:.85rem">{esc(text)}</span>',
            class_="ux-badge",
        )

    def set(self, count: int, *, label: str | None = None) -> Result:
        return self.refresh(count=count, label=label if label is not None else self.label)

    def _register(self) -> None:
        comp = self

        @self.ch.action(self.action_name("set"))
        def set_count(count: int = 0, label: str = "") -> Result:
            return comp.set(count, label=label or comp.label)
