"""ConfirmButton — dangerous once-cap action with optional modal."""

from __future__ import annotations

from typing import Any, Callable, Optional

from ux_channel.components.base import ChannelComponent
from ux_channel.components.modal import Modal
from ux_channel.render.html_safe import esc
from ux_channel.protocol.types import Result

OnConfirm = Callable[[], Result | None]



def _button(host, label, action, **kwargs):
    """HTML button via host.button or region_button (Channel has no HTML façade)."""
    btn = getattr(host, "button", None)
    if callable(btn):
        return btn(label, action, **kwargs)
    from ux_channel.components.primitive import region_button
    reg = getattr(host, "registry", host)
    return region_button(reg, label, action, **kwargs)

class Confirm(ChannelComponent):
    """
    One-shot dangerous action (delete, pay).

    ::

        conf = Confirm(ch, uid="Del:user", label="Delete",
                       action_verb="run", on_confirm=do_delete,
                       confirm_message="Delete this user?").install()
    """

    kind = "Confirm"

    def __init__(
        self,
        channel,
        *,
        uid: str | None = None,
        name: str = "Confirm",
        label: str = "Confirm",
        confirm_message: str = "Are you sure?",
        on_confirm: OnConfirm | None = None,
        use_modal: bool = True,
        once: bool = True,
    ):
        super().__init__(channel, uid=uid, name=name)
        self.label = label
        self.confirm_message = confirm_message
        self.on_confirm = on_confirm
        self.use_modal = use_modal
        self.once = once
        self._modal = Modal(channel, uid=f"{self.uid}:modal", title="Confirm") if use_modal else None

    def render(self, **state: Any) -> str:
        pending = bool(state.get("pending", False))
        modal_html = ""
        if self._modal:
            modal_html = self._modal.render(
                open=pending,
                body=f"<p>{esc(self.confirm_message)}</p>"
                f'<div style="display:flex;gap:.5rem;margin-top:1rem">'
                f'{_button(self.ch, "Cancel", self.action_name("cancel"), args={{}}, target=self.uid)}'
                f'{_button(self.ch, self.label, self.action_name("run"), args={{}}, target=self.uid, once=self.once)}'
                f"</div>",
                title="Confirm",
            )
        trigger = self.btn(self.label, "ask", trust={}, class_name="ux-confirm-trigger")
        return self.wrap(trigger + modal_html, class_="ux-confirm")

    def _register(self) -> None:
        comp = self
        if self._modal:
            self._modal.install()

        @self.ch.action(self.action_name("ask"))
        def ask() -> Result:
            return comp.refresh(pending=True)

        @self.ch.action(self.action_name("cancel"))
        def cancel() -> Result:
            return comp.refresh(pending=False)

        @self.ch.action(self.action_name("run"))
        def run() -> Result:
            if comp.on_confirm:
                out = comp.on_confirm()
                if isinstance(out, Result):
                    return out
            return comp.refresh(pending=False, notice="Done", notice_level="success")
