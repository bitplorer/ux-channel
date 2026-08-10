
"""SortableJS list bridge — drag-and-drop reordering for ux-dom lists."""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Sequence
from ux_channel.bridges._factory import BridgeFactoryMixin

__all__ = ["SortableBridge", "SORTABLE_PACKAGE"]
SORTABLE_PACKAGE = "sortablejs"
SORTABLE_METHODS = ("update", "destroy", "setOrder", "toArray")

@dataclass
class _State:
    items: list = field(default_factory=list)  # [{id, html|label}]
    animation: int = 150
    handle: str = ""
    ghost_class: str = "opacity-50"
    group: str = ""
    disabled: bool = False

class SortableBridge(BridgeFactoryMixin):
    package = SORTABLE_PACKAGE
    methods = SORTABLE_METHODS
    description = "SortableJS drag-and-drop list"

    def __init__(self, ch, id=None, *, items=None, animation=150, handle="",
                 ghost_class="opacity-50", group="", disabled=False, auto_register=True):
        super().__init__(
            ch, id, items=list(items or []), animation=animation, handle=handle,
            ghost_class=ghost_class, group=group, disabled=disabled,
            auto_register=auto_register,
        )

    def _new_state(self, **kw):
        return _State(**{k: v for k, v in kw.items() if k in _State.__dataclass_fields__})

    def _build_props(self):
        st = self._state
        items = []
        for it in st.items:
            if isinstance(it, dict):
                items.append({
                    "id": str(it.get("id", it.get("value", ""))),
                    "label": it.get("label", it.get("html", it.get("text", str(it.get("id", ""))))),
                    "html": it.get("html"),
                })
            else:
                items.append({"id": str(it), "label": str(it)})
        return {
            "items": items,
            "animation": int(st.animation),
            "handle": st.handle or None,
            "ghostClass": st.ghost_class,
            "group": st.group or None,
            "disabled": bool(st.disabled),
        }

    def set_order(self, ids: Sequence[str]):
        # reorder items list by ids
        by_id = {}
        for it in self._state.items:
            if isinstance(it, dict):
                by_id[str(it.get("id", it.get("value", "")))] = it
            else:
                by_id[str(it)] = it
        new_items = [by_id[i] for i in ids if i in by_id]
        self.configure(items=new_items)
        return self.fire("setOrder", list(ids))
