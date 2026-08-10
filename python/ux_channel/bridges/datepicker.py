
"""Flatpickr date/time bridge — scheduling and forms."""

from __future__ import annotations
from dataclasses import dataclass
from typing import Any
from ux_channel.bridges._factory import BridgeFactoryMixin

__all__ = ["DatePickerBridge", "DATEPICKER_PACKAGE"]
DATEPICKER_PACKAGE = "flatpickr"
DATEPICKER_METHODS = ("update", "destroy", "setDate", "clear", "open", "close")

@dataclass
class _State:
    value: str = ""
    mode: str = "single"  # single | range | multiple
    enable_time: bool = False
    date_format: str = "Y-m-d"
    min_date: str = ""
    max_date: str = ""
    inline: bool = False
    theme: str = "dark"

class DatePickerBridge(BridgeFactoryMixin):
    package = DATEPICKER_PACKAGE
    methods = DATEPICKER_METHODS
    description = "Flatpickr date picker"

    def __init__(self, ch, id=None, *, value="", mode="single", enable_time=False,
                 date_format="Y-m-d", min_date="", max_date="", inline=False,
                 theme="dark", auto_register=True):
        super().__init__(
            ch, id, value=value, mode=mode, enable_time=enable_time,
            date_format=date_format, min_date=min_date, max_date=max_date,
            inline=inline, theme=theme, auto_register=auto_register,
        )

    def _new_state(self, **kw):
        return _State(**{k: v for k, v in kw.items() if k in _State.__dataclass_fields__})

    def _build_props(self):
        st = self._state
        return {
            "value": st.value,
            "mode": st.mode,
            "enableTime": bool(st.enable_time),
            "dateFormat": st.date_format,
            "minDate": st.min_date or None,
            "maxDate": st.max_date or None,
            "inline": bool(st.inline),
            "theme": st.theme,
        }

    def set_date(self, value: str):
        self.configure(value=value)
        return self.fire("setDate", value)
