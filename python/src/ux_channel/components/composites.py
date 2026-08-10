"""
Complex composites — Channel widgets + slots for ux-dom / other libraries.

These are the **next layer** above Counter/Form/Flash:
domain-shaped panels that compose multiple channel regions and accept
foreign fragments in slots (media, chrome, custom rows).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Mapping, Optional, Sequence

from ux_channel.components.badge import Badge
from ux_channel.components.base import ChannelComponent
from ux_channel.components.compose import Composite, Block, Slot, fragment, join_fragments
from ux_channel.components.counter import Counter
from ux_channel.components.flash import Flash
from ux_channel.components.form import Field, Form
from ux_channel.components.list_view import ListView
from ux_channel.components.primitive import region_root, to_html
from ux_channel.render.html_safe import esc
from ux_channel.protocol.types import Result



def _button(host, label, action, **kwargs):
    """HTML button via host.button or region_button (Channel has no HTML façade)."""
    btn = getattr(host, "button", None)
    if callable(btn):
        return btn(label, action, **kwargs)
    from ux_channel.components.primitive import region_button
    reg = getattr(host, "registry", host)
    return region_button(reg, label, action, **kwargs)

class AppShell(Composite):
    """
    Application chrome: brand + nav + flash + main + sidebar slots.

    ::

        shell = AppShell(host, uid=\"App:shell\", slots={
            \"brand\": ux_dom_logo,
            \"nav\": \"<a href='/'>Home</a>\",
            \"main\": cart_panel,   # nested ChannelComponent
        }).install()
    """

    kind = "AppShell"
    slot_names = ("brand", "nav", "flash", "main", "sidebar", "footer")

    def layout(self, slots: Mapping[str, str], **state: Any) -> str:
        side = (
            f'<aside class="ux-shell-side" style="min-width:12rem">{slots.get("sidebar","")}</aside>'
            if slots.get("sidebar")
            else ""
        )
        return f"""
<header class="ux-shell-header" style="display:flex;justify-content:space-between;align-items:center;gap:1rem;padding:.75rem 0;border-bottom:1px solid #e2e8f0">
  <div class="ux-shell-brand">{slots.get("brand","")}</div>
  <nav class="ux-shell-nav" style="display:flex;gap:1rem">{slots.get("nav","")}</nav>
</header>
{slots.get("flash","")}
<div class="ux-shell-body" style="display:flex;gap:1.25rem;margin-top:1rem">
  <main class="ux-shell-main" style="flex:1;min-width:0">{slots.get("main","")}</main>
  {side}
</div>
<footer class="ux-shell-footer" style="margin-top:2rem;color:#64748b;font-size:.85rem">{slots.get("footer","")}</footer>
"""


class LoginCard(Composite):
    """
    Branded login: media/title slots + embedded Form + Flash.

    slots: title, subtitle, media, footer
    """

    kind = "LoginCard"
    slot_names = ("title", "subtitle", "media", "footer")

    def __init__(
        self,
        host: Any,
        *,
        uid: str = "LoginCard:root",
        name: str = "LoginCard",
        fields: list[Field] | None = None,
        validate: Callable | None = None,
        on_submit: Callable | None = None,
        success_redirect: str | None = "/app",
        slots: Mapping[str, Any] | None = None,
    ):
        super().__init__(host, uid=uid, name=name, slots=slots, class_name="ux-login-card")
        self.flash = Flash(host, uid=f"{uid}:flash", name=f"{name}Flash").install()
        self.form = Form(
            host,
            uid=f"{uid}:form",
            name=f"{name}Form",
            fields=fields
            or [
                Field("email", "Email", type="email", required=True),
                Field("password", "Password", type="password", required=True),
            ],
            validate=validate,
            on_submit=on_submit,
            success_redirect=success_redirect,
            submit_label="Sign in",
        ).install()

    def layout(self, slots: Mapping[str, str], **state: Any) -> str:
        title = slots.get("title") or "<h2 style='margin:0 0 .25rem'>Sign in</h2>"
        sub = slots.get("subtitle") or ""
        return f"""
<div style="display:grid;gap:1rem;max-width:22rem">
  {slots.get("media","")}
  <div>{title}{sub}</div>
  {self.flash.render(**state.get("flash", {}) if isinstance(state.get("flash"), dict) else {})}
  {self.form.render(
      values=state.get("values") or {},
      errors=state.get("errors") or {},
  )}
  {slots.get("footer","")}
</div>
"""


class CartPanel(Composite):
    """
    Cart: line list slot + qty Counter + Badge + checkout action.

    Domain state is passed into render / actions; lines can be ux-dom rows.
    """

    kind = "CartPanel"
    slot_names = ("header", "empty")

    def __init__(
        self,
        host: Any,
        *,
        uid: str = "Cart:panel",
        name: str = "Cart",
        on_checkout: Callable[[list[dict]], Result] | None = None,
        line_renderer: Callable[[dict], Any] | None = None,
        slots: Mapping[str, Any] | None = None,
    ):
        super().__init__(host, uid=uid, name=name, slots=slots, class_name="ux-cart-panel")
        self.on_checkout = on_checkout
        self.line_renderer = line_renderer or (
            lambda line: f"<li style='padding:.4rem 0;border-bottom:1px solid #e2e8f0'>"
            f"{esc(str(line.get('title', line)))} × {int(line.get('qty', 1))}</li>"
        )
        self.badge = Badge(host, uid=f"{uid}:badge", name=f"{name}Badge", label="Items").install()
        self.counter = Counter(
            host, uid=f"{uid}:qty", name=f"{name}Qty", min_value=0, max_value=99, show_reset=False
        ).install()

    def _lines_html(self, lines: Sequence[dict]) -> str:
        if not lines:
            empty = self.slot_html("empty") or "<p class='ux-cart-empty'>Cart is empty</p>"
            return empty
        return "<ul style='list-style:none;padding:0;margin:0'>" + "".join(
            fragment(self.line_renderer(line)) for line in lines
        ) + "</ul>"

    def render(self, **state: Any) -> str:
        lines = list(state.get("lines") or [])
        total_qty = sum(int(x.get("qty", 1)) for x in lines)
        header = self.slot_html("header") or "<strong>Cart</strong>"
        inner = f"""
<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:.75rem">
  {header}
  {self.badge.render(count=total_qty, label="Items")}
</div>
{self._lines_html(lines)}
<div style="margin-top:1rem;display:flex;gap:.5rem;align-items:center;flex-wrap:wrap">
  <span style="color:#64748b;font-size:.9rem">Quick qty</span>
  {self.counter.render(n=int(state.get("quick_qty", 1) or 1))}
  {_button(self.host, "Checkout", self.action_name("checkout"), args={"n": total_qty}, target=self.uid)}
</div>
"""
        return region_root(self.uid, inner, class_=self.class_name)

    def _register(self) -> None:
        comp = self

        @self.host.action(self.action_name("checkout"))
        def checkout(n: int = 0, **kwargs: Any) -> Result:
            lines = kwargs.get("lines") or []
            if comp.on_checkout:
                return comp.on_checkout(list(lines) if lines else [{"qty": n}])
            return comp.refresh(
                lines=[{"title": "Item", "qty": n}] if n else [],
                notice=("Checked out" if n else "Nothing to checkout"),
                notice_level=("success" if n else "info"),
            )

        @self.host.action(self.action_name("set_lines"))
        def set_lines(lines: list | None = None, **kwargs: Any) -> Result:
            return comp.refresh(lines=list(lines or []))


class DataTable(ChannelComponent):
    """
    Sortable / pageable table with row action hooks.

    ``row_cells`` may return str or ux-dom-like fragments per row.
    """

    kind = "DataTable"

    def __init__(
        self,
        host: Any,
        *,
        uid: str = "Table:root",
        name: str = "DataTable",
        columns: Sequence[str] | None = None,
        loader: Callable[[str, str, bool, int, int], tuple[Sequence[Any], int]] | None = None,
        row_cells: Callable[[Any], Sequence[Any]] | None = None,
        per_page: int = 10,
        row_actions: Callable[[Any], str] | None = None,
    ):
        super().__init__(host, uid=uid, name=name)
        self.columns = list(columns or ("id", "name"))
        self.loader = loader
        self.row_cells = row_cells or (lambda row: [getattr(row, c, row.get(c, "") if isinstance(row, dict) else "") for c in self.columns])
        self.per_page = per_page
        self.row_actions = row_actions

    def render(self, **state: Any) -> str:
        q = str(state.get("q", "") or "")
        sort = str(state.get("sort", self.columns[0] if self.columns else "id") or "id")
        desc = bool(state.get("desc", False))
        page = max(1, int(state.get("page", 1) or 1))
        rows: Sequence[Any] = state.get("rows") or []
        total = int(state.get("total", len(rows)) or 0)
        if self.loader and "rows" not in state:
            rows, total = self.loader(q, sort, desc, page, self.per_page)
        pages = max(1, (total + self.per_page - 1) // self.per_page) if total else 1

        head_cells = []
        for col in self.columns:
            arrow = ""
            if col == sort:
                arrow = " ↓" if desc else " ↑"
            head_cells.append(
                f"<th style='text-align:left;padding:.4rem'>"
                f"{_button(self.host, esc(col) + arrow, self.action_name('sort'), args={'q': q, 'sort': col, 'desc': (not desc) if col == sort else False, 'page': 1}, target=self.uid)}"
                f"</th>"
            )
        if self.row_actions:
            head_cells.append("<th></th>")

        body_rows = []
        for row in rows:
            cells = self.row_cells(row)
            tds = "".join(
                f"<td style='padding:.4rem;border-top:1px solid #e2e8f0'>{fragment(c)}</td>"
                for c in cells
            )
            if self.row_actions:
                tds += f"<td style='padding:.4rem;border-top:1px solid #e2e8f0'>{self.row_actions(row)}</td>"
            body_rows.append(f"<tr>{tds}</tr>")

        pager = []
        if page > 1:
            pager.append(
                _button(self.host, 
                    "Prev",
                    self.action_name("page"),
                    args={"q": q, "sort": sort, "desc": desc, "page": page - 1},
                    target=self.uid,
                )
            )
        pager.append(f"<span>Page {page}/{pages}</span>")
        if page < pages:
            pager.append(
                _button(self.host, 
                    "Next",
                    self.action_name("page"),
                    args={"q": q, "sort": sort, "desc": desc, "page": page + 1},
                    target=self.uid,
                )
            )

        inner = f"""
<div style="display:flex;gap:.5rem;margin-bottom:.5rem">
  <input value="{esc(q)}" id="{esc(self.uid)}-q" style="flex:1;padding:.4rem" placeholder="Filter…"/>
  {_button(self.host, "Filter", self.action_name("page"), args={"q": q, "sort": sort, "desc": desc, "page": 1}, target=self.uid)}
</div>
<table class="ux-datatable" style="width:100%;border-collapse:collapse;font-size:.95rem">
  <thead><tr>{"".join(head_cells)}</tr></thead>
  <tbody>{"".join(body_rows) if body_rows else f'<tr><td colspan="{len(self.columns)+1}" style="padding:.75rem;color:#64748b">No rows</td></tr>'}</tbody>
</table>
<div style="display:flex;gap:.5rem;align-items:center;margin-top:.5rem">{"".join(pager)}</div>
"""
        return region_root(self.uid, inner, class_="ux-datatable-wrap")

    def _load(self, q: str, sort: str, desc: bool, page: int) -> Result:
        rows: Sequence[Any] = []
        total = 0
        if self.loader:
            rows, total = self.loader(q, sort, desc, page, self.per_page)
        return self.refresh(q=q, sort=sort, desc=desc, page=page, rows=list(rows), total=total)

    def _register(self) -> None:
        comp = self

        @self.host.action(self.action_name("page"))
        def page(q: str = "", sort: str = "id", desc: bool = False, page: int = 1) -> Result:
            return comp._load(q, sort, bool(desc), max(1, int(page or 1)))

        @self.host.action(self.action_name("sort"))
        def sort(q: str = "", sort: str = "id", desc: bool = False, page: int = 1) -> Result:
            return comp._load(q, sort, bool(desc), max(1, int(page or 1)))


class Dashboard(Composite):
    """
    Multi-panel dashboard: arbitrary named panels as slots + optional Tabs.

    ::

        dash = Dashboard(host, uid=\"Dash:root\", panels={
            \"sales\": sales_region,
            \"orders\": orders_table,
        }).install()
    """

    kind = "Dashboard"

    def __init__(
        self,
        host: Any,
        *,
        uid: str = "Dash:root",
        name: str = "Dashboard",
        panels: Mapping[str, Any] | None = None,
        title: str = "Dashboard",
    ):
        slots = dict(panels or {})
        super().__init__(host, uid=uid, name=name, slots=slots, class_name="ux-dashboard")
        self.title = title
        for p in slots.values():
            if isinstance(p, ChannelComponent):
                p.install()

    def layout(self, slots: Mapping[str, str], **state: Any) -> str:
        cards = []
        for name, html in slots.items():
            cards.append(
                f'<section class="ux-dash-panel" style="border:1px solid #e2e8f0;border-radius:12px;'
                f'padding:1rem;margin-bottom:1rem">'
                f'<h3 style="margin:0 0 .75rem;font-size:.95rem;color:#334155">{esc(name.title())}</h3>'
                f"{html}</section>"
            )
        return f"<h2 style='margin:0 0 1rem'>{esc(self.title)}</h2>" + "".join(cards)


class MediaCard(Composite):
    """
    Card with media slot (perfect for ux-dom image trees) + channel actions.

    slots: media, title, body, meta
    """

    kind = "MediaCard"
    slot_names = ("media", "title", "body", "meta")

    def __init__(
        self,
        host: Any,
        *,
        uid: str,
        name: str = "MediaCard",
        primary_action: str | None = None,
        primary_label: str = "Select",
        primary_args: dict | None = None,
        slots: Mapping[str, Any] | None = None,
    ):
        super().__init__(host, uid=uid, name=name, slots=slots, class_name="ux-media-card")
        self.primary_action = primary_action
        self.primary_label = primary_label
        self.primary_args = primary_args or {}

    def layout(self, slots: Mapping[str, str], **state: Any) -> str:
        action = ""
        if self.primary_action:
            action = _button(self.host, 
                self.primary_label,
                self.primary_action,
                trust=self.primary_args,
                target=self.uid,
            )
        return f"""
<article style="border:1px solid #e2e8f0;border-radius:12px;overflow:hidden;max-width:18rem">
  <div class="ux-media">{slots.get("media","")}</div>
  <div style="padding:.85rem">
    <div style="font-weight:600">{slots.get("title","")}</div>
    <div style="color:#64748b;font-size:.9rem;margin:.35rem 0">{slots.get("body","")}</div>
    <div style="display:flex;justify-content:space-between;align-items:center;gap:.5rem">
      <span style="font-size:.85rem">{slots.get("meta","")}</span>
      {action}
    </div>
  </div>
</article>
"""
