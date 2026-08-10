
"""CodeMirror 6-style editor bridge (CDN adapter) — code UIs for ux-dom."""

from __future__ import annotations
from dataclasses import dataclass
from typing import Any
from ux_channel.bridges._factory import BridgeFactoryMixin

__all__ = ["CodeMirrorBridge", "CODEMIRROR_PACKAGE"]
CODEMIRROR_PACKAGE = "codemirror"
CODEMIRROR_METHODS = ("update", "destroy", "setValue", "getValue", "focus")

@dataclass
class _State:
    value: str = ""
    language: str = "javascript"
    theme: str = "dark"
    line_numbers: bool = True
    read_only: bool = False
    tab_size: int = 2

class CodeMirrorBridge(BridgeFactoryMixin):
    package = CODEMIRROR_PACKAGE
    methods = CODEMIRROR_METHODS
    description = "CodeMirror editor"

    def __init__(self, ch, id=None, *, value="", language="javascript", theme="dark",
                 line_numbers=True, read_only=False, tab_size=2, auto_register=True):
        super().__init__(
            ch, id, value=value, language=language, theme=theme,
            line_numbers=line_numbers, read_only=read_only, tab_size=tab_size,
            auto_register=auto_register,
        )

    def _new_state(self, **kw):
        return _State(**{k: v for k, v in kw.items() if k in _State.__dataclass_fields__})

    def _build_props(self):
        st = self._state
        return {
            "value": st.value,
            "language": st.language,
            "theme": st.theme,
            "lineNumbers": bool(st.line_numbers),
            "readOnly": bool(st.read_only),
            "tabSize": int(st.tab_size),
        }

    def set_value(self, value: str, **kw):
        self.configure(value=value, **kw)
        return self.fire("setValue", value)
