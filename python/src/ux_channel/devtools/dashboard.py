# Copyright (c) 2026 UX-CHANNEL
#
# This software is released under the MIT License.
# https://opensource.org/licenses/MIT
"""DX Dashboard — observe-only operator surface for **ux-channel**.
Brand: PyPI ``ux-channel`` · import ``ux_channel`` · CLI ``uxchannel``.
This is **not product UI**. It answers a fixed set of operator jobs:
1. **Status** — Can I trust this process right now?
2. **Guidance** — What should I fix next? (actionable hints only)
3. **Performance** — Is the hot path within budget? (only when…"""

from __future__ import annotations

import html
import importlib
import os
import threading
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Iterable, Mapping, Protocol, Sequence, runtime_checkable

from ux_channel.protocol import serde as _serde

__all__ = [
    "Context",
    "Panel",
    "Widget",
    "Extension",
    "register_plugin",
    "unregister_plugin",
    "clear_plugins",
    "list_plugins",
    "configure_dashboard",
    "get_dashboard_settings",
    "reset_dashboard_settings",
    "load_plugins_from_env",
    "build_dashboard_model",
    "render_dashboard_html",
    "write_dashboard",
    "run_dashboard_suite",
    "USE_CASES",
    "DASHBOARD_MODEL_SCHEMA",
]


# Snapshot model format (JSON ``schema`` field). Not Intent/Result protocol.
# Bump only when model shape breaks consumers. 0.1 = 1.
DASHBOARD_MODEL_SCHEMA: int = 1

# Ordered operator jobs the dashboard answers.
USE_CASES: tuple[dict[str, str], ...] = (
    {
        "id": "status",
        "question": "Can I trust this process right now?",
        "shows": "ok · environment · one-line summary",
    },
    {
        "id": "guidance",
        "question": "What should I fix next?",
        "shows": "doctor hints · next steps",
    },
    {
        "id": "performance",
        "question": "Is the hot path within budget?",
        "shows": "p50/p95/p99 only when samples exist",
    },
    {
        "id": "inventory",
        "question": "What surface is registered?",
        "shows": "actions · regions · path · media mode",
    },
    {
        "id": "policy",
        "question": "Are safety defaults sane?",
        "shows": "require_cap · memory stores · observe (never secrets)",
    },
    {
        "id": "observability",
        "question": "Are OpenTelemetry / channel traces flowing?",
        "shows": "observe mode · OTel attach · recent frame digest (no payloads)",
    },
    {
        "id": "subsystems",
        "question": "Are bridge / media / webrtc quiet?",
        "shows": "shallow diagnose digests",
    },
    {
        "id": "extensions",
        "question": "What does my team care about?",
        "shows": "registered plugins only",
    },
)


def _esc(value: Any) -> str:
    return html.escape("" if value is None else str(value), quote=True)


def _fmt(value: Any) -> str:
    if isinstance(value, float):
        return f"{value:.4g}"
    if isinstance(value, (dict, list, tuple)):
        try:
            return _serde.dumps(value)
        except Exception:
            return str(value)
    return str(value)


class _FmtMap(dict):
    def __missing__(self, key: str) -> str:
        return ""


# data


@dataclass
class Context:
    """Read-only inputs. Extensions must not mutate Channel through this."""

    doctor: dict[str, Any] = field(default_factory=dict)
    latencies: list[dict[str, Any]] = field(default_factory=list)
    runtime: dict[str, Any] = field(default_factory=dict)
    extras: dict[str, Any] = field(default_factory=dict)
    # Pre-computed sections (integrity view). Extensions may read; not required.
    sections: dict[str, Any] = field(default_factory=dict)


@dataclass
class Panel:
    """Presentation unit projected from a section or extension."""

    id: str
    title: str
    kind: str = "html"  # html | svg | table | json
    order: int = 100
    html: str = ""
    svg: str = ""
    rows: list[tuple[str, Any]] = field(default_factory=list)
    data: Any = None
    span: int = 1
    plugin_id: str = ""
    css: str = ""
    use_case: str = ""  # status|guidance|performance|inventory|policy|subsystems|extensions

    @staticmethod
    def as_table(
        id: str,
        title: str,
        rows: Sequence[tuple[str, Any]],
        *,
        order: int = 100,
        span: int = 1,
        use_case: str = "",
    ) -> Panel:
        return Panel(
            id=id, title=title, kind="table", order=order, rows=list(rows), span=span, use_case=use_case
        )

    @staticmethod
    def as_html(
        id: str,
        title: str,
        markup: str,
        *,
        order: int = 100,
        span: int = 1,
        css: str = "",
        use_case: str = "",
    ) -> Panel:
        return Panel(
            id=id, title=title, kind="html", order=order, html=markup, span=span, css=css, use_case=use_case
        )

    @staticmethod
    def as_svg(
        id: str,
        title: str,
        markup: str,
        *,
        order: int = 100,
        span: int = 2,
        use_case: str = "",
    ) -> Panel:
        return Panel(
            id=id, title=title, kind="svg", order=order, svg=markup, span=span, use_case=use_case
        )

    @staticmethod
    def as_json(
        id: str,
        title: str,
        data: Any,
        *,
        order: int = 100,
        span: int = 1,
        use_case: str = "",
    ) -> Panel:
        return Panel(
            id=id, title=title, kind="json", order=order, data=data, span=span, use_case=use_case
        )

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["rows"] = [[k, v] for k, v in self.rows]
        d["span"] = 2 if self.span >= 2 else 1
        return d

    @classmethod
    def from_mapping(cls, raw: Mapping[str, Any]) -> Panel:
        rows: list[tuple[str, Any]] = []
        for item in raw.get("rows") or []:
            if isinstance(item, (list, tuple)) and len(item) >= 2:
                rows.append((str(item[0]), item[1]))
        return cls(
            id=str(raw.get("id") or "panel"),
            title=str(raw.get("title") or ""),
            kind=str(raw.get("kind") or "html"),
            order=int(raw.get("order") or 100),
            html=str(raw.get("html") or ""),
            svg=str(raw.get("svg") or ""),
            rows=rows,
            data=raw.get("data"),
            span=2 if int(raw.get("span") or 1) >= 2 else 1,
            plugin_id=str(raw.get("plugin_id") or ""),
            css=str(raw.get("css") or ""),
            use_case=str(raw.get("use_case") or ""),
        )


@dataclass
class Widget:
    """Team extension unit: data in, HTML out. No JS."""

    id: str
    title: str
    props: dict[str, Any] = field(default_factory=dict)
    body: str | None = None
    css: str = ""
    order: int = 100
    span: int = 1
    plugin_id: str = ""
    use_case: str = "extensions"

    def to_panel(self) -> Panel:
        if self.body is not None and str(self.body).strip() != "":
            flat = {str(k): _fmt(v) for k, v in self.props.items()}
            try:
                inner = _esc(str(self.body).format_map(_FmtMap(flat)))
            except Exception:
                inner = _esc(str(self.body))
        elif self.props:
            parts = [
                f"<div class='ux-dx-kv'><span class='k'>{_esc(k)}</span>"
                f"<span class='v'>{_esc(_fmt(v))}</span></div>"
                for k, v in self.props.items()
            ]
            inner = f"<div class='ux-dx-props'>{''.join(parts)}</div>"
        else:
            inner = '<span class="muted">(no data)</span>'

        data_attrs = []
        for k, v in self.props.items():
            if isinstance(v, (dict, list, tuple)) or v is None:
                continue
            key = "".join(c if c.isalnum() else "-" for c in str(k)).strip("-").lower()
            if not key:
                continue
            if isinstance(v, bool):
                data_attrs.append(f'data-{_esc(key)}="{"true" if v else "false"}"')
            elif isinstance(v, (int, float, str)):
                data_attrs.append(f'data-{_esc(key)}="{_esc(v)}"')

        markup = (
            f'<div class="ux-dx-view" data-channel-dx-widget="{_esc(self.id)}" '
            f'{" ".join(data_attrs)}>{inner}</div>'
        )
        return Panel(
            id=self.id,
            title=self.title,
            kind="html",
            order=self.order,
            html=markup,
            span=self.span,
            plugin_id=self.plugin_id,
            css=self.css,
            use_case=self.use_case or "extensions",
        )


# sections (integrity core)


_SECRET_KEYS = frozenset(
    {
        "secret",
        "token",
        "password",
        "api_key",
        "apikey",
        "authorization",
        "private_key",
        "cookie",
        "csrf",
    }
)


def _scrub(obj: Any, *, depth: int = 0) -> Any:
    """Drop secret-like keys; cap depth. Integrity: never dump credentials."""
    if depth > 3:
        return "…"
    if isinstance(obj, Mapping):
        out: dict[str, Any] = {}
        for k, v in obj.items():
            lk = str(k).lower()
            if any(s in lk for s in _SECRET_KEYS):
                out[str(k)] = "«redacted»"
            else:
                out[str(k)] = _scrub(v, depth=depth + 1)
        return out
    if isinstance(obj, (list, tuple)):
        return [_scrub(x, depth=depth + 1) for x in list(obj)[:20]]
    if isinstance(obj, (str, int, float, bool)) or obj is None:
        return obj
    return str(type(obj).__name__)


def build_sections(
    *,
    doctor: Mapping[str, Any],
    latencies: Sequence[Mapping[str, Any]],
    runtime: Mapping[str, Any],
) -> dict[str, Any]:
    """Compute the use-case sections — source of truth for the dashboard."""
    doc = dict(doctor or {})
    diag = doc.get("diagnose") if isinstance(doc.get("diagnose"), dict) else {}
    if not isinstance(diag, dict):
        diag = {}

    ok = bool(doc.get("ok", True))
    env = str(doc.get("environment") or diag.get("environment") or "unknown")
    if doc.get("error"):
        ok = False
        summary = f"unhealthy: {doc.get('error')}"
    elif ok:
        summary = f"healthy · {env}"
    else:
        summary = f"not ok · {env}"

    hints = [str(h) for h in (doc.get("hints") or []) if h][:12]
    next_steps = [str(x) for x in (doc.get("next") or []) if x][:8]

    lats = [dict(x) for x in (latencies or [])]
    perf_available = bool(lats)

    # Inventory — prefer doctor top-level, fall back to diagnose
    actions = diag.get("actions")
    if actions is None:
        actions = doc.get("actions")
    regions = doc.get("regions")
    if regions is None:
        regions = diag.get("regions")

    inventory = {
        "path": doc.get("path") or diag.get("path") or "—",
        "action_endpoint": diag.get("action_endpoint") or "—",
        "actions": actions if actions is not None else "—",
        "regions": regions if regions is not None else "—",
        "media_mode": doc.get("media_mode") or "—",
        "public_api": doc.get("public_api") or "—",
    }

    policy = {
        "environment": env,
        "require_cap": diag.get("require_cap"),
        "allow_memory_stores": diag.get("allow_memory_stores"),
        "observe": diag.get("observe"),
        "serde": runtime.get("serde"),
        "wire_engines": runtime.get("wire_engines"),
        "parallel_enabled": runtime.get("parallel_enabled"),
        "batch_parallel": runtime.get("batch_parallel"),
        "max_workers": runtime.get("max_workers"),
        "max_in_flight": runtime.get("max_in_flight"),
    }
    # Drop Nones so empty policy fields don't look like false claims
    policy = {k: v for k, v in policy.items() if v is not None}

    subsystems = {}
    for name in ("webrtc", "media", "bridge", "presence", "state", "live_bindings"):
        if name in diag and diag[name] not in (None, {}, []):
            subsystems[name] = _scrub(diag[name])

    # Observability: OTel + channel tracer (prefer live snapshot over stale diagnose alone)
    try:
        from ux_channel.devtools.otel import dashboard_snapshot as _otel_dash

        observability = _otel_dash(frame_limit=12)
    except Exception as exc:
        observability = {
            "otel": {"available": False, "attached": False, "error": str(exc)[:120]},
            "channel_tracer": {"enabled": False, "recent": []},
            "guidance": ["observability snapshot unavailable"],
        }
    # merge diagnose.otel if present
    if isinstance(diag.get("otel"), dict):
        observability.setdefault("otel", {}).update(
            {k: v for k, v in diag["otel"].items() if k not in observability.get("otel", {})}
        )
    # observe mode from policy/doctor
    observability["observe_mode"] = policy.get("observe") or doc.get("observe") or diag.get("observe")

    return {
        "status": {
            "ok": ok,
            "level": "ok" if ok else "error",
            "environment": env,
            "summary": summary,
        },
        "guidance": {
            "hints": hints,
            "next": next_steps,
            "available": bool(hints or next_steps),
        },
        "performance": {
            "available": perf_available,
            "latencies": lats,
            "note": None
            if perf_available
            else "No samples — run `uxchannel dashboard` (with profile) or `uxchannel profile`.",
        },
        "inventory": inventory,
        "policy": policy,
        "observability": observability,
        "subsystems": {
            "available": bool(subsystems),
            "items": subsystems,
        },
        "use_cases": list(USE_CASES),
    }


# extension contract


@runtime_checkable
class Extension(Protocol):
    id: str

    def contribute(self, ctx: Context) -> Any: ...


def _normalize(result: Any, *, plugin_id: str) -> list[Panel]:
    if result is None:
        return []
    if isinstance(result, (Panel, Widget)):
        items = [result]
    elif isinstance(result, Sequence) and not isinstance(result, (str, bytes)):
        items = list(result)
    else:
        return []
    panels: list[Panel] = []
    for item in items:
        if isinstance(item, Widget):
            if not item.plugin_id:
                item.plugin_id = plugin_id
            panel = item.to_panel()
        elif isinstance(item, Panel):
            panel = item
        elif isinstance(item, Mapping) and item.get("id"):
            panel = Panel.from_mapping(item)
        else:
            continue
        if not panel.plugin_id:
            panel.plugin_id = plugin_id
        if not panel.use_case and not panel.plugin_id.startswith("builtin."):
            panel.use_case = "extensions"
        panels.append(panel)
    return panels


def _safe_contribute(ext: Extension, ctx: Context) -> list[Panel]:
    pid = str(getattr(ext, "id", "") or "").strip() or "anon"
    try:
        return _normalize(ext.contribute(ctx), plugin_id=pid)
    except Exception as exc:
        return [
            Panel.as_html(
                f"error.{pid}",
                f"Extension error: {pid}",
                f"<p class='muted'>Extension failed: {_esc(exc)}</p>",
                order=9999,
                use_case="extensions",
            )
        ]


# registry


@dataclass(frozen=True)
class DashboardSettings:
    builtins_enabled: bool = True
    enabled_plugins: frozenset[str] | None = None
    disabled_plugins: frozenset[str] = frozenset()
    shell: str = "default"
    title: str = "ux-channel DX Dashboard"


class _Registry:
    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._ext: dict[str, Extension] = {}
        self._settings = DashboardSettings()
        self._env_loaded = False
        self._builtins = False

    def settings(self) -> DashboardSettings:
        with self._lock:
            return self._settings

    def configure(self, **kwargs: Any) -> DashboardSettings:
        with self._lock:
            cur = self._settings
            self._settings = DashboardSettings(
                builtins_enabled=bool(kwargs["builtins_enabled"])
                if "builtins_enabled" in kwargs
                else cur.builtins_enabled,
                enabled_plugins=frozenset(kwargs["enabled_plugins"])
                if "enabled_plugins" in kwargs
                else cur.enabled_plugins,
                disabled_plugins=frozenset(kwargs["disabled_plugins"])
                if "disabled_plugins" in kwargs
                else cur.disabled_plugins,
                shell=str(kwargs["shell"]) if "shell" in kwargs else cur.shell,
                title=str(kwargs["title"]) if "title" in kwargs else cur.title,
            )
            return self._settings

    def reset_settings(self) -> DashboardSettings:
        with self._lock:
            self._settings = DashboardSettings()
            self._env_loaded = False
            return self._settings

    def register(self, ext: Extension, *, replace: bool = True) -> None:
        pid = str(getattr(ext, "id", "") or "").strip()
        if not pid:
            raise ValueError("Extension.id is required")
        if not callable(getattr(ext, "contribute", None)):
            raise TypeError("Extension.contribute(ctx) is required")
        with self._lock:
            if not replace and pid in self._ext:
                raise ValueError(f"already registered: {pid}")
            self._ext[pid] = ext

    def unregister(self, plugin_id: str) -> bool:
        with self._lock:
            return self._ext.pop(str(plugin_id), None) is not None

    def clear(self, *, keep_builtins: bool = False) -> None:
        with self._lock:
            self._ext.clear()
            self._builtins = False
        if keep_builtins:
            self.ensure_builtins()

    def list(self) -> list[dict[str, Any]]:
        self.prepare()
        with self._lock:
            items = list(self._ext.values())
        items.sort(key=lambda e: (int(getattr(e, "order", 100) or 100), str(e.id)))
        return [
            {
                "id": e.id,
                "title": getattr(e, "title", e.id),
                "order": int(getattr(e, "order", 100) or 100),
            }
            for e in items
        ]

    def enabled(self) -> list[Extension]:
        self.prepare()
        s = self.settings()
        with self._lock:
            items = list(self._ext.values())
        out: list[Extension] = []
        for ext in items:
            pid = str(ext.id)
            if pid in s.disabled_plugins:
                continue
            if s.enabled_plugins is not None and pid not in s.enabled_plugins:
                continue
            if not s.builtins_enabled and pid.startswith("builtin."):
                continue
            out.append(ext)
        out.sort(key=lambda e: (int(getattr(e, "order", 100) or 100), str(e.id)))
        return out

    def prepare(self) -> None:
        if self.settings().builtins_enabled:
            self.ensure_builtins()
        with self._lock:
            need = not self._env_loaded
            if need:
                self._env_loaded = True
        if need:
            load_plugins_from_env()

    def ensure_builtins(self) -> None:
        with self._lock:
            if self._builtins and any(k.startswith("builtin.") for k in self._ext):
                return
            for ext in _builtins():
                self._ext[ext.id] = ext
            self._builtins = True


_REG = _Registry()


def register_plugin(plugin: Extension, *, replace: bool = True) -> None:
    _REG.register(plugin, replace=replace)


def unregister_plugin(plugin_id: str) -> bool:
    return _REG.unregister(plugin_id)


def clear_plugins(*, keep_builtins: bool = False) -> None:
    _REG.clear(keep_builtins=keep_builtins)


def list_plugins() -> list[dict[str, Any]]:
    return _REG.list()


def configure_dashboard(**kwargs: Any) -> DashboardSettings:
    return _REG.configure(**kwargs)


def get_dashboard_settings() -> DashboardSettings:
    return _REG.settings()


def reset_dashboard_settings() -> DashboardSettings:
    return _REG.reset_settings()


def load_plugins_from_env(spec: str | None = None) -> list[str]:
    raw = spec if spec is not None else os.environ.get("UX_CHANNEL_DX_PLUGINS", "")
    loaded: list[str] = []
    for part in (raw or "").split(","):
        part = part.strip()
        if not part or ":" not in part:
            continue
        mod_name, _, attr = part.partition(":")
        try:
            mod = importlib.import_module(mod_name)
            factory = getattr(mod, attr)
            result = factory() if callable(factory) else factory
            batch = result if isinstance(result, (list, tuple)) else [result]
            for ext in batch:
                register_plugin(ext)
                loaded.append(str(getattr(ext, "id", part)))
        except Exception:
            continue
    return loaded


# built-in pack: project sections → panels (use-case order)


def _svg_bars(latencies: Sequence[Mapping[str, Any]], *, w: int = 640, h: int = 220) -> str:
    if not latencies:
        return (
            f'<svg viewBox="0 0 {w} {h}" width="100%" role="img">'
            f'<text x="16" y="40" fill="#94a3b8" font-size="14">No latency samples</text></svg>'
        )
    max_p95 = max(float(x.get("p95_ms") or 0) for x in latencies) or 1.0
    n = len(latencies)
    pl, pr, pt, pb = 48, 16, 24, 64
    pw, ph = w - pl - pr, h - pt - pb
    gap = 12
    bw = max(8.0, (pw - gap * (n - 1)) / n)
    parts = [
        f'<svg viewBox="0 0 {w} {h}" width="100%" role="img" aria-label="p95 latency" '
        f'font-family="system-ui,sans-serif">'
        f'<rect width="{w}" height="{h}" fill="#0f172a" rx="12"/>'
        f'<text x="{pl}" y="18" fill="#94a3b8" font-size="12">p95 ms (lower is better)</text>'
    ]
    for frac in (0.0, 0.5, 1.0):
        y = pt + ph * (1 - frac)
        parts.append(
            f'<line x1="{pl}" y1="{y:.1f}" x2="{w - pr}" y2="{y:.1f}" stroke="#1e293b"/>'
            f'<text x="8" y="{y + 4:.1f}" fill="#64748b" font-size="10">{max_p95 * frac:.2f}</text>'
        )
    for i, lat in enumerate(latencies):
        p95 = float(lat.get("p95_ms") or 0)
        p50 = float(lat.get("p50_ms") or 0)
        h95 = (p95 / max_p95) * ph
        h50 = (p50 / max_p95) * ph
        x = pl + i * (bw + gap)
        name = str(lat.get("name") or f"op{i}")
        short = name if len(name) <= 18 else name[:16] + "…"
        parts.append(
            f'<rect x="{x:.1f}" y="{pt + ph - h95:.1f}" width="{bw:.1f}" '
            f'height="{max(h95, 1):.1f}" fill="#6366f1" rx="4">'
            f"<title>{_esc(name)} p95={p95}</title></rect>"
            f'<rect x="{x + bw * 0.25:.1f}" y="{pt + ph - h50:.1f}" width="{bw * 0.5:.1f}" '
            f'height="{max(h50, 1):.1f}" fill="#22d3ee" rx="3"/>'
            f'<text x="{x + bw / 2:.1f}" y="{h - 36}" fill="#cbd5e1" font-size="10" '
            f'text-anchor="middle">{_esc(short)}</text>'
            f'<text x="{x + bw / 2:.1f}" y="{h - 20}" fill="#818cf8" font-size="10" '
            f'text-anchor="middle">{p95:.2f}</text>'
        )
    parts.append("</svg>")
    return "".join(parts)


class _BuiltinSections:
    """Single built-in extension: projects integrity sections into panels."""

    id = "builtin.sections"
    title = "Core"
    order = 0

    def contribute(self, ctx: Context) -> list[Panel]:
        s = ctx.sections or {}
        panels: list[Panel] = []

        # 1. STATUS
        st = s.get("status") or {}
        level = st.get("level") or ("ok" if st.get("ok") else "error")
        badge = "ok" if level == "ok" else "bad"
        panels.append(
            Panel.as_html(
                "core.status",
                "Status",
                (
                    f"<div class='status status-{badge}'>"
                    f"<span class='dot'></span>"
                    f"<div><div class='summary'>{_esc(st.get('summary'))}</div>"
                    f"<div class='muted'>environment: {_esc(st.get('environment'))}</div></div>"
                    f"</div>"
                ),
                order=1,
                span=2,
                use_case="status",
            )
        )

        # 2. GUIDANCE
        g = s.get("guidance") or {}
        if g.get("available"):
            hints = g.get("hints") or []
            nxt = g.get("next") or []
            body = ""
            if hints:
                body += "<p class='muted'><b>Hints</b></p><ul>" + "".join(
                    f"<li>{_esc(h)}</li>" for h in hints
                ) + "</ul>"
            if nxt:
                body += "<p class='muted'><b>Next</b></p><ul>" + "".join(
                    f"<li>{_esc(h)}</li>" for h in nxt
                ) + "</ul>"
            panels.append(
                Panel.as_html("core.guidance", "Guidance", body, order=2, span=2, use_case="guidance")
            )
        else:
            panels.append(
                Panel.as_html(
                    "core.guidance",
                    "Guidance",
                    "<p class='muted'>No doctor hints — nothing urgent from diagnose.</p>",
                    order=2,
                    span=2,
                    use_case="guidance",
                )
            )

        # 3. PERFORMANCE
        perf = s.get("performance") or {}
        if perf.get("available"):
            lats = perf.get("latencies") or []
            rows_html = "".join(
                f"<tr><td>{_esc(x.get('name'))}</td><td>{_esc(x.get('p50_ms'))}</td>"
                f"<td><b>{_esc(x.get('p95_ms'))}</b></td><td>{_esc(x.get('p99_ms'))}</td>"
                f"<td>{_esc(x.get('mean_ms'))}</td></tr>"
                for x in lats
            )
            table = (
                "<table><tr><th>bench</th><th>p50</th><th>p95</th><th>p99</th><th>mean</th></tr>"
                f"{rows_html}</table>"
            )
            panels.append(
                Panel.as_svg(
                    "core.performance.chart",
                    "Performance (p95 / p50)",
                    _svg_bars(lats),
                    order=10,
                    use_case="performance",
                )
            )
            panels.append(
                Panel.as_html(
                    "core.performance.table",
                    "Performance table",
                    table,
                    order=11,
                    span=2,
                    use_case="performance",
                )
            )
        else:
            panels.append(
                Panel.as_html(
                    "core.performance",
                    "Performance",
                    f"<p class='muted'>{_esc(perf.get('note'))}</p>",
                    order=10,
                    span=2,
                    use_case="performance",
                )
            )

        # 4. INVENTORY
        inv = s.get("inventory") or {}
        panels.append(
            Panel.as_table(
                "core.inventory",
                "Inventory",
                [(k, inv[k]) for k in ("path", "action_endpoint", "actions", "regions", "media_mode", "public_api") if k in inv],
                order=20,
                use_case="inventory",
            )
        )

        # 5. POLICY (runtime + safety-ish flags — scrubbed)
        pol = s.get("policy") or {}
        if pol:
            panels.append(
                Panel.as_table(
                    "core.policy",
                    "Policy & runtime",
                    list(pol.items()),
                    order=30,
                    use_case="policy",
                )
            )

        # 6. OBSERVABILITY (OpenTelemetry + channel frames)
        obs = s.get("observability") or {}
        otel = obs.get("otel") or {}
        ctr = obs.get("channel_tracer") or {}
        obs_rows = [
            ("observe_mode", obs.get("observe_mode")),
            ("otel_available", otel.get("available")),
            ("otel_attached", otel.get("attached")),
            ("otel_provider", otel.get("provider")),
            ("open_request_spans", otel.get("open_request_spans")),
            ("channel_tracer_enabled", ctr.get("enabled")),
            ("recent_frames", ctr.get("recent_count")),
            ("error_frames", ctr.get("error_frames")),
        ]
        obs_rows = [(k, v) for k, v in obs_rows if v is not None]
        panels.append(
            Panel.as_table(
                "core.observability",
                "Observability (OpenTelemetry)",
                obs_rows or [("status", "no data")],
                order=35,
                use_case="observability",
            )
        )
        tips = obs.get("guidance") or []
        recent = ctr.get("recent") or []
        recent_html = ""
        if recent:
            rows = "".join(
                f"<tr><td>{_esc(r.get('seq'))}</td><td>{_esc(r.get('kind'))}</td>"
                f"<td>{_esc(r.get('action'))}</td><td>{_esc(r.get('ok'))}</td>"
                f"<td>{_esc(r.get('duration_ms'))}</td></tr>"
                for r in recent[-12:]
            )
            recent_html = (
                "<p class='muted'><b>Recent channel frames</b> (no payloads)</p>"
                "<table><tr><th>seq</th><th>kind</th><th>action</th><th>ok</th><th>ms</th></tr>"
                f"{rows}</table>"
            )
        tips_html = (
            "<ul>" + "".join(f"<li>{_esc(x)}</li>" for x in tips) + "</ul>" if tips else ""
        )
        if recent_html or tips_html:
            panels.append(
                Panel.as_html(
                    "core.observability.tail",
                    "Trace tail",
                    tips_html + recent_html,
                    order=36,
                    span=2,
                    use_case="observability",
                )
            )

        # 7. SUBSYSTEMS
        sub = s.get("subsystems") or {}
        if sub.get("available"):
            items = sub.get("items") or {}
            # one compact json panel — honest shallow digests
            panels.append(
                Panel.as_json(
                    "core.subsystems",
                    "Subsystems",
                    items,
                    order=40,
                    span=2,
                    use_case="subsystems",
                )
            )
        else:
            panels.append(
                Panel.as_html(
                    "core.subsystems",
                    "Subsystems",
                    "<p class='muted'>No subsystem diagnose data in this snapshot.</p>",
                    order=40,
                    use_case="subsystems",
                )
            )

        return panels


def _builtins() -> list[Extension]:
    return [_BuiltinSections()]


# pipeline


def _runtime_snapshot() -> dict[str, Any]:
    from ux_channel.transport.concurrency import get_concurrency_settings
    from ux_channel.wire import available_engines, get_codec

    conc = get_concurrency_settings()
    codec = get_codec()
    return {
        "serde": codec.name,
        "wire_engines": available_engines(),
        "parallel_enabled": conc.parallel_enabled,
        "max_workers": conc.max_workers,
        "batch_parallel": conc.batch_parallel,
        "max_in_flight": conc.max_in_flight,
    }


def build_dashboard_model(
    *,
    doctor: Mapping[str, Any] | None = None,
    latencies: Sequence[Mapping[str, Any]] | None = None,
    extras: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Compose model: sections (integrity) + panels (presentation). Schema 3."""
    settings = _REG.settings()
    runtime = _runtime_snapshot()
    doc = dict(doctor or {})
    lats = [dict(x) for x in (latencies or [])]
    sections = build_sections(doctor=doc, latencies=lats, runtime=runtime)

    ctx = Context(
        doctor=doc,
        latencies=lats,
        runtime=runtime,
        extras=dict(extras or {}),
        sections=sections,
    )

    panels: list[Panel] = []
    for ext in _REG.enabled():
        panels.extend(_safe_contribute(ext, ctx))
    panels.sort(key=lambda p: (p.order, p.id))

    assets: list[dict[str, Any]] = []
    for p in panels:
        if (p.css or "").strip():
            assets.append(
                {
                    "plugin_id": p.plugin_id,
                    "name": f"{p.id}.css",
                    "kind": "css",
                    "content": p.css,
                }
            )

    return {
        "schema": DASHBOARD_MODEL_SCHEMA,
        "purpose": "observe-only DX snapshot for ux-channel operators",
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "brand": {"pypi": "ux-channel", "import": "ux_channel", "cli": "uxchannel"},
        "settings": {
            "builtins_enabled": settings.builtins_enabled,
            "shell": settings.shell,
            "title": settings.title,
        },
        "use_cases": list(USE_CASES),
        "sections": sections,
        "plugins": list_plugins(),
        "doctor": doc,
        "latencies": lats,
        "runtime": runtime,
        "extras": ctx.extras,
        "panels": [p.to_dict() for p in panels],
        "assets": assets,
        "integrity": [
            "observe-only",
            "no secrets",
            "missing performance is labeled, not invented",
            "model is source of truth; shell is optional",
        ],
    }


# shell


def _render_panel(panel: Panel) -> str:
    span = " span-2" if panel.span >= 2 else ""
    uc = f' data-use-case="{_esc(panel.use_case)}"' if panel.use_case else ""
    head = (
        f'<section class="card{span}" data-panel-id="{_esc(panel.id)}" '
        f'data-plugin="{_esc(panel.plugin_id)}"{uc}><h2>{_esc(panel.title)}</h2>'
    )
    if panel.kind == "svg":
        body = panel.svg
    elif panel.kind == "table":
        rows = "".join(
            f"<tr><th>{_esc(k)}</th><td><code>{_esc(v)}</code></td></tr>" for k, v in panel.rows
        )
        body = f'<table class="kv">{rows}</table>'
    elif panel.kind == "json":
        body = f"<pre>{_esc(_serde.dumps(panel.data, pretty=True))}</pre>"
    else:
        body = panel.html
    return head + body + "</section>"


_SHELL_CSS = """
:root{--bg:#020617;--card:#0f172a;--line:#1e293b;--text:#e2e8f0;--muted:#94a3b8;--ok:#34d399;--bad:#f87171}
*{box-sizing:border-box}
body{margin:0;font-family:system-ui,sans-serif;background:
  radial-gradient(1000px 500px at 10% -10%,#1e1b4b,transparent 50%),var(--bg);
  color:var(--text);min-height:100vh}
header,footer,main{max-width:1100px;margin:0 auto;padding:1rem 1.5rem}
header h1{margin:0 0 .25rem;font-size:1.35rem}
.brand{display:flex;flex-wrap:wrap;gap:.4rem;margin-top:.6rem}
.pill{background:#1e293b;border:1px solid #334155;border-radius:999px;
  padding:.15rem .6rem;font-size:.75rem;color:#c7d2fe}
main{display:grid;gap:1rem;grid-template-columns:1.3fr 1fr}
@media(max-width:860px){main{grid-template-columns:1fr}}
.card{background:var(--card);border:1px solid var(--line);border-radius:16px;padding:1rem}
.card.span-2{grid-column:1/-1}
.card h2{margin:0 0 .75rem;font-size:.95rem;color:#c7d2fe}
table{width:100%;border-collapse:collapse;font-size:.85rem}
th,td{text-align:left;padding:.35rem;border-bottom:1px solid var(--line)}
th{color:var(--muted);font-weight:500}
table.kv th{width:42%}
.muted{color:var(--muted);font-size:.9rem}
code,pre{font-family:ui-monospace,monospace;font-size:.8rem}
pre{background:#020617;border:1px solid var(--line);border-radius:10px;
  padding:.75rem;overflow:auto;max-height:280px}
ul{color:var(--muted);margin:.25rem 0 0;padding-left:1.1rem}
.status{display:flex;gap:.75rem;align-items:flex-start}
.status .dot{width:.75rem;height:.75rem;border-radius:999px;margin-top:.35rem;flex:none}
.status-ok .dot{background:var(--ok);box-shadow:0 0 12px var(--ok)}
.status-bad .dot{background:var(--bad);box-shadow:0 0 12px var(--bad)}
.status .summary{font-size:1.1rem;font-weight:600}
.ux-dx-view{display:block}
.ux-dx-props{display:grid;gap:.35rem}
.ux-dx-kv{display:flex;justify-content:space-between;gap:1rem;
  padding:.35rem 0;border-bottom:1px solid var(--line);font-size:.9rem}
.ux-dx-kv .k{color:var(--muted)}
.ux-dx-kv .v{font-family:ui-monospace,monospace;color:#e0e7ff}
"""


def render_dashboard_html(model: Mapping[str, Any]) -> str:
    settings = _REG.settings()
    shell = str((model.get("settings") or {}).get("shell") or settings.shell)

    if shell == "none":
        return (
            "<!doctype html><title>model-only</title>"
            "<p>shell=none — consume sections in your own UI.</p>"
            f"<pre>{_esc(_serde.dumps(model, pretty=True))}</pre>"
        )

    brand = model.get("brand") or {}
    panels = [Panel.from_mapping(p) for p in (model.get("panels") or [])]
    cards = "\n".join(_render_panel(p) for p in panels)
    styles = []
    for asset in model.get("assets") or []:
        if str(asset.get("kind")) == "css" and asset.get("content"):
            styles.append(
                f'<style data-channel-dx-asset="{_esc(asset.get("name"))}">{asset["content"]}</style>'
            )

    title = (model.get("settings") or {}).get("title") or settings.title
    st = (model.get("sections") or {}).get("status") or {}
    purpose = model.get("purpose") or "observe-only DX"
    plugins_html = ", ".join(_esc(p.get("id")) for p in (model.get("plugins") or [])) or "(none)"
    integrity = model.get("integrity") or []
    integrity_html = " · ".join(_esc(x) for x in integrity)
    raw = _esc(_serde.dumps(model, pretty=True))
    minimal = shell == "minimal"

    chrome = "" if minimal else f"""
<header>
  <h1>{_esc(title)}</h1>
  <p>{_esc(purpose)}</p>
  <div class="brand">
    <span class="pill">PyPI {_esc(brand.get('pypi'))}</span>
    <span class="pill">import {_esc(brand.get('import'))}</span>
    <span class="pill">CLI {_esc(brand.get('cli'))}</span>
    <span class="pill">model v{_esc(model.get('schema'))}</span>
    <span class="pill">{_esc(model.get('generated_at'))}</span>
    <span class="pill">status: {_esc(st.get('level') or '—')}</span>
  </div>
  <p class="muted" style="margin-top:.75rem">Plugins: {plugins_html}</p>
</header>
"""
    footer = "" if minimal else f"""
<footer>
  <p class="muted">{integrity_html}</p>
  <details><summary class="muted">Raw model JSON (sections + panels)</summary><pre>{raw}</pre></details>
</footer>
"""
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>{_esc(title)}</title>
{"".join(styles)}
<style>{_SHELL_CSS}</style>
</head>
<body data-channel-dx-dashboard="1" data-channel-dx-schema="{_esc(model.get('schema'))}">
{chrome}
<main id="ux-dx-root">
{cards}
</main>
{footer}
</body>
</html>
"""


def write_dashboard(
    out_dir: Path | str,
    *,
    model: Mapping[str, Any] | None = None,
    doctor: Mapping[str, Any] | None = None,
    latencies: Sequence[Mapping[str, Any]] | None = None,
) -> Path:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    m = dict(model) if model else build_dashboard_model(doctor=doctor, latencies=latencies)
    (out / "dashboard.html").write_text(render_dashboard_html(m), encoding="utf-8")
    (out / "dashboard.json").write_text(_serde.dumps(m, pretty=True) + "\n", encoding="utf-8")
    return out / "dashboard.html"


def run_dashboard_suite(
    *,
    out_dir: Path | str | None = None,
    include_profile: bool = True,
    rounds: int = 40,
    warmup: int = 4,
    profile_rounds: int = 15,
    doctor: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """CLI: optional profile samples + doctor → sections + shell."""
    out = Path(out_dir) if out_dir else Path.cwd() / "reports" / "dx"
    out.mkdir(parents=True, exist_ok=True)

    latencies: list[dict[str, Any]] = []
    if include_profile:
        from ux_channel.transport.batch import dispatch_batch
        from ux_channel.transport.concurrency import dispatch_parallel
        from ux_channel.devtools.profiling import run_suite
        from ux_channel.host.registry import ActionRegistry
        from ux_channel.protocol.types import Intent, Result

        reg = ActionRegistry(
            secret="test-secret-key-32chars-minimum!!!!",
            require_cap=False,
        )

        @reg.action("echo")
        def echo(ctx, n: int = 0):
            return Result.success(n=n)

        intents = [
            Intent(action="echo", args={"n": i}, request_id=f"r{i}") for i in range(24)
        ]
        items = [
            {"action": "echo", "args": {"n": i}, "request_id": f"b{i}"} for i in range(12)
        ]
        report = run_suite(
            [
                (
                    "dispatch_one",
                    lambda: reg.dispatch(
                        Intent(action="echo", args={"n": 0}, request_id="solo")
                    ),
                ),
                ("dispatch_parallel_24", lambda: dispatch_parallel(reg, intents)),
                ("dispatch_batch_12", lambda: dispatch_batch(reg, items)),
            ],
            out_dir=out / "p95",
            title="ux-channel dashboard profile",
            rounds=rounds,
            warmup=warmup,
            profile_rounds=profile_rounds,
        )
        latencies = list(report.get("latencies") or [])

    doc = dict(doctor) if doctor is not None else {}
    if not doc:
        try:
            from fastapi import FastAPI

            from ux_channel import Channel, ChannelConfig

            ch = Channel.boot(
                FastAPI(),
                config=ChannelConfig.development(
                    secret="dashboard-dev-secret-key-32chars!!!!",
                    allow_memory_stores=True,
                ),
            )
            doc = ch.doctor()
        except Exception as exc:
            doc = {"ok": False, "error": f"doctor unavailable: {exc}"}

    model = build_dashboard_model(doctor=doc, latencies=latencies)
    path = write_dashboard(out, model=model)
    model["artifacts"] = {
        "html": str(path.resolve()),
        "json": str((out / "dashboard.json").resolve()),
        "p95": str((out / "p95").resolve()) if include_profile else None,
    }
    return model
