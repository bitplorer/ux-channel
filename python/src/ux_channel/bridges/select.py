
"""Searchable select bridge (Tom Select-compatible adapter) — forms that feel native."""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Sequence
from ux_channel.bridges._factory import BridgeFactoryMixin

__all__ = ["SelectBridge", "SELECT_PACKAGE"]
SELECT_PACKAGE = "tom-select"
SELECT_METHODS = ("update", "destroy", "setValue", "clear", "enable", "disable")

@dataclass
class _State:
    options: list = field(default_factory=list)  # [{value, label}] or strings
    value: Any = None
    multiple: bool = False
    placeholder: str = "Select…"
    max_items: int | None = None
    create: bool = False
    theme: str = "default"

class SelectBridge(BridgeFactoryMixin):
    package = SELECT_PACKAGE
    methods = SELECT_METHODS
    description = "Tom Select searchable select"

    def __init__(self, ch, id=None, *, options=None, value=None, multiple=False,
                 placeholder="Select…", max_items=None, create=False, theme="default",
                 auto_register=True):
        super().__init__(
            ch, id,
            options=list(options or []),
            value=value,
            multiple=multiple,
            placeholder=placeholder,
            max_items=max_items,
            create=create,
            theme=theme,
            auto_register=auto_register,
        )

    def _new_state(self, **kw):
        return _State(**{k: v for k, v in kw.items() if k in _State.__dataclass_fields__})

    def _build_props(self):
        st = self._state
        # inline normalize without Mapping import issue
        opts = []
        for o in st.options:
            if isinstance(o, dict):
                opts.append({
                    "value": o.get("value", o.get("id")),
                    "label": o.get("label", o.get("text", str(o.get("value", "")))),
                })
            elif isinstance(o, (list, tuple)) and len(o) >= 2:
                opts.append({"value": o[0], "label": o[1]})
            else:
                opts.append({"value": o, "label": str(o)})
        return {
            "options": opts,
            "value": st.value,
            "multiple": bool(st.multiple),
            "placeholder": st.placeholder,
            "maxItems": st.max_items,
            "create": bool(st.create),
            "theme": st.theme,
        }

    def set_value(self, value):
        self.configure(value=value)
        return self.fire("setValue", value)

    def clear(self):
        self.configure(value=None if not self._state.multiple else [])
        return self.fire("clear")
