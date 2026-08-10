
"""Quill rich-text bridge — documents and comments."""

from __future__ import annotations
from dataclasses import dataclass
from typing import Any
from ux_channel.bridges._factory import BridgeFactoryMixin

__all__ = ["QuillBridge", "QUILL_PACKAGE"]
QUILL_PACKAGE = "quill"
QUILL_METHODS = ("update", "destroy", "setContents", "setText", "enable")

@dataclass
class _State:
    html: str = ""
    theme: str = "snow"
    placeholder: str = "Write…"
    read_only: bool = False
    toolbar: bool = True

class QuillBridge(BridgeFactoryMixin):
    package = QUILL_PACKAGE
    methods = QUILL_METHODS
    description = "Quill rich text editor"

    def __init__(self, ch, id=None, *, html="", theme="snow", placeholder="Write…",
                 read_only=False, toolbar=True, auto_register=True):
        super().__init__(
            ch, id, html=html, theme=theme, placeholder=placeholder,
            read_only=read_only, toolbar=toolbar, auto_register=auto_register,
        )

    def _new_state(self, **kw):
        return _State(**{k: v for k, v in kw.items() if k in _State.__dataclass_fields__})

    def _build_props(self):
        st = self._state
        return {
            "html": st.html,
            "theme": st.theme,
            "placeholder": st.placeholder,
            "readOnly": bool(st.read_only),
            "toolbar": bool(st.toolbar),
        }

    def set_html(self, html: str):
        self.configure(html=html)
        return self.fire("setContents", html)
