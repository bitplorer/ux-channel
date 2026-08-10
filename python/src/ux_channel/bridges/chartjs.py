"""
Chart.js **bridge preset** — data-first, no HTML.

Application (feels natural)::

    charts = ChartBridge(ch)                 # bind channel once
    rev = charts("revenue", labels=[...], values=[...], kind="bar")

    @ch.on
    def refresh():
        return rev.commit(values=[4, 9, 14])

    # Chart.js styling that the library supports → options= (not invented css=)
    # rev.commit(options={"plugins": {"legend": {"display": False}}})
    spec = rev.mount_spec()                   # ux-dom styles the host element

One-shot still works::

    rev = ChartBridge(ch, "revenue", values=[1, 2, 3])
"""

from __future__ import annotations

import copy
from dataclasses import dataclass, field
from typing import Any, Mapping, Optional, Sequence

from ux_channel.render.placement import Placement

__all__ = [
    "ChartBridge",
    "ChartSeries",
    "CHART_PACKAGE",
    "CHART_METHODS",
    "THEMES",
]

CHART_PACKAGE = "chart.js"
CHART_METHODS = ("update", "destroy", "setType", "setData")

THEMES: dict[str, dict[str, str]] = {
    "indigo": {
        "bg": "rgba(99, 102, 241, 0.65)",
        "border": "rgb(79, 70, 229)",
    },
    "emerald": {
        "bg": "rgba(16, 185, 129, 0.65)",
        "border": "rgb(5, 150, 105)",
    },
    "rose": {
        "bg": "rgba(244, 63, 94, 0.65)",
        "border": "rgb(225, 29, 72)",
    },
    "slate": {
        "bg": "rgba(100, 116, 139, 0.65)",
        "border": "rgb(71, 85, 105)",
    },
}

_KIND = {
    "bar": "bar",
    "line": "line",
    "doughnut": "doughnut",
    "donut": "doughnut",
    "pie": "pie",
    "area": "line",
}


@dataclass
class ChartSeries:
    label: str
    values: list[float | int]
    color: str | None = None


@dataclass
class _State:
    labels: list[str] = field(default_factory=list)
    values: list[float | int] = field(default_factory=list)
    series: list[ChartSeries] = field(default_factory=list)
    kind: str = "bar"
    title: str = ""
    theme: str = "indigo"
    series_label: str = "Series"
    options: dict[str, Any] = field(default_factory=dict)


def _state_from_kwargs(
    *,
    labels: Sequence[str] | None = None,
    values: Sequence[float | int] | None = None,
    series: Sequence[ChartSeries] | None = None,
    kind: str = "bar",
    title: str = "",
    theme: str = "indigo",
    series_label: str = "Series",
    options: Mapping[str, Any] | None = None,
) -> _State:
    return _State(
        labels=list(labels or []),
        values=list(values or []),
        series=list(series or []),
        kind=kind,
        title=title,
        theme=theme,
        series_label=series_label,
        options=dict(options or {}),
    )


class ChartBridge:
    """
    Chart.js without learning Chart.js — bridge data plane only.

    * ``ChartBridge(ch)`` — factory bound to a channel
    * ``charts("rev", …)`` — one chart island
    * ``rev.commit(…)`` — ``ch.done`` + bridge ops (no glue)
    """

    def __init__(
        self,
        ch: Any,
        id: str | None = None,
        *,
        labels: Sequence[str] | None = None,
        values: Sequence[float | int] | None = None,
        series: Sequence[ChartSeries] | None = None,
        kind: str = "bar",
        title: str = "",
        theme: str = "indigo",
        series_label: str = "Series",
        options: Mapping[str, Any] | None = None,
        auto_register: bool = True,
    ) -> None:
        if ch is None:
            raise ValueError("ChartBridge requires a Channel instance (from Channel.boot)")
        self.ch = ch
        self._defaults = dict(
            labels=list(labels or []) if labels is not None else None,
            values=list(values or []) if values is not None else None,
            series=list(series or []) if series is not None else None,
            kind=kind,
            title=title,
            theme=theme,
            series_label=series_label,
            options=dict(options) if options is not None else None,
        )
        # drop Nones from defaults so instance kwargs win cleanly
        self._defaults = {k: v for k, v in self._defaults.items() if v is not None}

        if id is None:
            # factory: ChartBridge(ch) only — defaults may still be set
            self.id = ""
            self._factory = True
            self._state = _state_from_kwargs(**{  # type: ignore[arg-type]
                "kind": kind,
                "title": title,
                "theme": theme,
                "series_label": series_label,
                **{k: v for k, v in self._defaults.items()},
            })
            return

        if not str(id).strip():
            raise ValueError(
                "ChartBridge island id is required; use ChartBridge(ch) for a factory, "
                "then charts('revenue', …)"
            )
        self._factory = False
        self.id = str(id).strip()
        self._state = _state_from_kwargs(
            labels=labels,
            values=values,
            series=series,
            kind=kind,
            title=title,
            theme=theme,
            series_label=series_label,
            options=options,
        )
        if auto_register:
            self.register()

# factory

    def __call__(self, id: str, **kwargs: Any) -> "ChartBridge":
        """
        Create a chart island on this channel::

            charts = ChartBridge(ch)
            rev = charts("revenue", values=[1, 2, 3], kind="bar")
        """
        if not id or not str(id).strip():
            raise ValueError("chart island id is required, e.g. charts('revenue', …)")
        # factory defaults, then per-island overrides
        base = {
            "kind": self._state.kind,
            "title": self._state.title,
            "theme": self._state.theme,
            "series_label": self._state.series_label,
            "labels": list(self._state.labels) or None,
            "values": list(self._state.values) or None,
            "series": list(self._state.series) or None,
            "options": dict(self._state.options) or None,
        }
        base = {k: v for k, v in base.items() if v is not None}
        base.update(kwargs)
        return ChartBridge(self.ch, str(id).strip(), auto_register=True, **base)  # type: ignore[arg-type]

    def _require_island(self) -> None:
        if getattr(self, "_factory", False) or not self.id:
            raise TypeError(
                "ChartBridge is a factory — create an island first: "
                "charts = ChartBridge(ch); rev = charts('revenue', values=[…])"
            )

# register / configure

    def register(self) -> "ChartBridge":
        self.ch.bridge.register(
            CHART_PACKAGE,
            methods=CHART_METHODS,
            description="Chart.js bridge preset (no HTML)",
        )
        return self

    def configure(
        self,
        *,
        labels: Sequence[str] | None = None,
        values: Sequence[float | int] | None = None,
        series: Sequence[ChartSeries] | None = None,
        kind: str | None = None,
        title: str | None = None,
        theme: str | None = None,
        series_label: str | None = None,
        options: Mapping[str, Any] | None = None,
    ) -> "ChartBridge":
        self._require_island()
        st = self._state
        if labels is not None:
            st.labels = list(labels)
        if values is not None:
            st.values = list(values)
        if series is not None:
            st.series = list(series)
        if kind is not None:
            st.kind = kind
        if title is not None:
            st.title = title
        if theme is not None:
            st.theme = theme
        if series_label is not None:
            st.series_label = series_label
        if options is not None:
            st.options = dict(options)
        return self

# ops (lists) — power users

    def set_values(
        self,
        values: Sequence[float | int],
        *,
        labels: Sequence[str] | None = None,
        title: str | None = None,
        kind: str | None = None,
        theme: str | None = None,
    ) -> list:
        self.configure(
            values=values, labels=labels, title=title, kind=kind, theme=theme
        )
        return self.update_ops()

    def set_kind(self, kind: str) -> list:
        self.configure(kind=kind)
        ops = self.update_ops()
        ops.extend(
            self.ch.bridge.call(
                self.id,
                "setType",
                self._chart_js_type(),
                package=CHART_PACKAGE,
            )
        )
        return ops

    def set_theme(self, theme: str) -> list:
        self.configure(theme=theme)
        return self.update_ops()

    def cycle_kind(self, order: Sequence[str] | None = None) -> list:
        order = list(order or ("bar", "line", "doughnut"))
        cur = self._state.kind
        try:
            i = order.index(cur)
        except ValueError:
            i = -1
        return self.set_kind(order[(i + 1) % len(order)])

    def cycle_theme(self, order: Sequence[str] | None = None) -> list:
        order = list(order or tuple(THEMES.keys()))
        cur = self._state.theme
        try:
            i = order.index(cur)
        except ValueError:
            i = -1
        return self.set_theme(order[(i + 1) % len(order)])

    def props(self) -> dict[str, Any]:
        self._require_island()
        return self._build_props()

    def mount_spec(self) -> Placement:
        """Placement (attrs) — **not** HTML. ux-dom consumes this."""
        self._require_island()
        return self.ch.bridge.mount_spec(
            self.id,
            package=CHART_PACKAGE,
            props=self.props(),
        )


    def mount_ops(self) -> list:
        self._require_island()
        return self.ch.bridge.mount_ops(
            self.id, CHART_PACKAGE, props=self.props()
        )

    def update_ops(self) -> list:
        self._require_island()
        return self.ch.bridge.update_ops(self.id, self.props())

    def update(self, **props: Any) -> list:
        """Merge chart fields and return bridge.update ops."""
        if props:
            known = {
                k: props[k]
                for k in (
                    "labels",
                    "values",
                    "series",
                    "kind",
                    "title",
                    "theme",
                    "series_label",
                    "options",
                )
                if k in props
            }
            self.configure(**known)
        return self.update_ops()

# commit — hides ch.done(*)

    def _result_with_ops(self, ops: list, *, notice: str | None = None) -> Any:
        """Merge bridge ops into a success Result (ch.done does not take *ops)."""
        from ux_channel.protocol.types import Result

        base = self.ch.done(notice=notice) if notice else self.ch.done()
        base_ops = list(base.ops or [])
        return Result(
            ok=True,
            ops=base_ops + list(ops),
            meta=dict(base.meta or {}),
            v=getattr(base, "v", None) or "1",
        )

    def commit(self, **props: Any) -> Any:
        """
        Apply chart props (optional) and return a success Result with bridge ops.

        ::

            return rev.commit(values=[4, 9, 14], title="Q1")
            return rev.commit(values=[1], notice="Updated")
        """
        self._require_island()
        notice = props.pop("notice", None)
        ops = self.update(**props) if props else self.update_ops()
        return self._result_with_ops(ops, notice=notice)

    def commit_values(self, values: Sequence[float | int], **kwargs: Any) -> Any:
        notice = kwargs.pop("notice", None)
        return self._result_with_ops(self.set_values(values, **kwargs), notice=notice)

    def commit_kind(self, kind: str, *, notice: str | None = None) -> Any:
        return self._result_with_ops(self.set_kind(kind), notice=notice)

    def commit_theme(self, theme: str, *, notice: str | None = None) -> Any:
        return self._result_with_ops(self.set_theme(theme), notice=notice)

    def commit_mount(self, *, notice: str | None = None) -> Any:
        """First paint: mount ops on a success Result."""
        return self._result_with_ops(self.mount_ops(), notice=notice)

    def adapter_src(self, default: str = "/demo-static/chartjs-adapter.js") -> str:
        return default

    def describe(self) -> dict[str, Any]:
        if self._factory:
            return {
                "mode": "factory",
                "api": [
                    "charts = ChartBridge(ch)",
                    "rev = charts('revenue', values=[…], kind='bar')",
                    "return rev.commit(values=[…])",
                    "spec = rev.mount_spec()  # ux-dom",
                ],
            }
        return {
            "mode": "island",
            "id": self.id,
            "package": CHART_PACKAGE,
            "kind": self._state.kind,
            "theme": self._state.theme,
            "title": self._state.title,
            "labels": list(self._state.labels),
            "values": list(self._state.values),
            "api": [
                "return rev.commit(values=[…])",
                "return rev.commit_kind('line')",
                "rev.mount_spec()  # ux-dom",
            ],
            "ui": "Build host in ux-dom from mount_spec().attrs",
            "themes": list(THEMES),
            "kinds": list(_KIND),
        }

# Chart.js mapping (hidden)

    def _chart_js_type(self) -> str:
        k = (self._state.kind or "bar").lower()
        return _KIND.get(k, k)

    def _theme_colors(self) -> dict[str, str]:
        return THEMES.get(self._state.theme, THEMES["indigo"])

    def _build_props(self) -> dict[str, Any]:
        st = self._state
        colors = self._theme_colors()
        chart_type = self._chart_js_type()
        fill = st.kind.lower() == "area"
        if st.series:
            datasets = [
                {
                    "label": ser.label,
                    "data": list(ser.values),
                    "backgroundColor": ser.color or colors["bg"],
                    "borderColor": ser.color or colors["border"],
                    "borderWidth": 2,
                    "borderRadius": 8,
                    "tension": 0.35,
                    "fill": fill,
                }
                for ser in st.series
            ]
        else:
            datasets = [
                {
                    "label": st.series_label,
                    "data": list(st.values),
                    "backgroundColor": colors["bg"],
                    "borderColor": colors["border"],
                    "borderWidth": 2,
                    "borderRadius": 8,
                    "tension": 0.35,
                    "fill": fill,
                }
            ]
        props: dict[str, Any] = {
            "type": chart_type,
            "title": st.title,
            "labels": list(st.labels),
            "datasets": datasets,
        }
        if st.options:
            props["options"] = copy.deepcopy(st.options)
        return props

    def __repr__(self) -> str:
        if self._factory:
            return f"ChartBridge(factory, ch={type(self.ch).__name__})"
        return (
            f"ChartBridge(id={self.id!r}, kind={self._state.kind!r}, "
            f"theme={self._state.theme!r})"
        )
