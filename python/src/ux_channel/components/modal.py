"""Modal / drawer chrome component."""

from __future__ import annotations

from typing import Any

from ux_channel.components.base import ChannelComponent
from ux_channel.render.html_safe import esc
from ux_channel.protocol.types import Result


class Modal(ChannelComponent):
    """
    Open/close modal shell. Content is HTML string or callable.

    ::

        m = Modal(ch, uid="Confirm:modal", title="Confirm delete").install()
        return m.open(body="<p>Are you sure?</p>")
        return m.close()
    """

    kind = "Modal"

    def __init__(
        self,
        channel,
        *,
        uid: str | None = None,
        name: str = "Modal",
        title: str = "",
        close_on_backdrop: bool = True,
    ):
        super().__init__(channel, uid=uid, name=name)
        self.title = title
        self.close_on_backdrop = close_on_backdrop

    def render(self, **state: Any) -> str:
        open_ = bool(state.get("open", False))
        body = str(state.get("body", "") or "")
        title = str(state.get("title", self.title) or "")
        if not open_:
            return self.wrap("", class_="ux-modal ux-modal-closed", hidden="hidden")
        close_btn = self.btn("×", "close", trust={}, class_name="ux-modal-x")
        return self.wrap(
            f'<div class="ux-modal-backdrop" style="position:fixed;inset:0;background:rgba(15,23,42,.45);'
            f'display:flex;align-items:center;justify-content:center;z-index:50">'
            f'<div class="ux-modal-panel" role="dialog" aria-modal="true" '
            f'style="background:#fff;border-radius:12px;padding:1.25rem;min-width:16rem;max-width:28rem;'
            f'box-shadow:0 20px 40px rgba(0,0,0,.15)">'
            f'<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:.75rem">'
            f'<strong id="modal-title">{esc(title)}</strong>{close_btn}</div>'
            f'<div class="ux-modal-body">{body}</div>'
            f"</div></div>",
            class_="ux-modal ux-modal-open",
        )

    def open(self, body: str = "", *, title: str | None = None, notice: str | None = None) -> Result:
        r = self.refresh(
            open=True,
            body=body,
            title=title if title is not None else self.title,
            notice=notice,
        )
        # also focus title for a11y
        return (
            self.ch.ui.region(self.uid, self.render(open=True, body=body, title=title or self.title))
            .focus("#modal-title")
            .dispatch_event("modal:opened", detail={"uid": self.uid})
            .ok()
        )

    def close(self, *, notice: str | None = None) -> Result:
        html = self.render(open=False)
        b = self.ch.ui.region(self.uid, html).dispatch_event("modal:closed", detail={"uid": self.uid})
        if notice:
            b.toast(notice)
        return b.ok()

    def _register(self) -> None:
        comp = self

        @self.ch.action(self.action_name("close"))
        def close() -> Result:
            return comp.close()

        @self.ch.action(self.action_name("open"))
        def open_act(body: str = "", title: str = "") -> Result:
            return comp.open(body=body, title=title or comp.title)
