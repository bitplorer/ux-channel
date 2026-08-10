"""Flash / banner region for persistent messages."""

from __future__ import annotations

from typing import Any

from ux_channel.components.base import ChannelComponent
from ux_channel.render.html_safe import esc
from ux_channel.protocol.types import Result

_LEVEL_STYLES = {
    "info": "background:#eff6ff;color:#1e40af;border:1px solid #bfdbfe",
    "success": "background:#ecfdf5;color:#065f46;border:1px solid #a7f3d0",
    "error": "background:#fef2f2;color:#991b1b;border:1px solid #fecaca",
    "warning": "background:#fffbeb;color:#92400e;border:1px solid #fde68a",
}


class Flash(ChannelComponent):
    """
    Persistent banner (unlike toast which is chrome-only).

    ::

        flash = Flash(ch, uid="App:flash").install()
        return flash.show("Saved", level="success")
        return flash.clear()
    """

    kind = "Flash"

    def render(self, **state: Any) -> str:
        msg = state.get("message")
        level = str(state.get("level", "info") or "info")
        if not msg:
            return self.wrap("", class_="ux-flash ux-flash-empty", hidden="hidden")
        style = _LEVEL_STYLES.get(level, _LEVEL_STYLES["info"])
        dismiss = self.btn("Dismiss", "clear", trust={}, class_name="ux-flash-x")
        return self.wrap(
            f'<div role="status" style="padding:.75rem 1rem;border-radius:8px;display:flex;'
            f'justify-content:space-between;gap:1rem;align-items:center;{style}">'
            f"<span>{esc(str(msg))}</span>{dismiss}</div>",
            class_=f"ux-flash ux-flash-{level}",
        )

    def show(self, message: str, *, level: str = "info") -> Result:
        return self.refresh(message=message, level=level)

    def clear(self) -> Result:
        return self.refresh(message=None)

    def _register(self) -> None:
        comp = self

        @self.ch.action(self.action_name("clear"))
        def clear() -> Result:
            return comp.clear()

        @self.ch.action(self.action_name("show"))
        def show(message: str = "", level: str = "info") -> Result:
            return comp.show(message, level=level)
