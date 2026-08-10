"""ListView — searchable / pageable list region."""

from __future__ import annotations

from typing import Any, Callable, Sequence

from ux_channel.components.base import ChannelComponent
from ux_channel.render.html_safe import esc, user_content
from ux_channel.protocol.ops import push_url
from ux_channel.protocol.types import Result

RowRenderer = Callable[[Any], str]
Loader = Callable[[str, int, int], tuple[Sequence[Any], int]]



def _button(host, label, action, **kwargs):
    """HTML button via host.button or region_button (Channel has no HTML façade)."""
    btn = getattr(host, "button", None)
    if callable(btn):
        return btn(label, action, **kwargs)
    from ux_channel.components.primitive import region_button
    reg = getattr(host, "registry", host)
    return region_button(reg, label, action, **kwargs)

class ListView(ChannelComponent):
    """
    Drop-in list with search + pagination actions.

    ::

        def load(q, page, per_page):
            items = db.search(q)[(page-1)*per_page:page*per_page]
            return items, total

        lv = ListView(ch, uid="Catalog:list", loader=load,
                      row=lambda it: f"<li>{it.name}</li>").install()
    """

    kind = "ListView"

    def __init__(
        self,
        channel,
        *,
        uid: str | None = None,
        name: str = "ListView",
        loader: Loader | None = None,
        row: RowRenderer | None = None,
        per_page: int = 10,
        empty_text: str = "No results",
        path_prefix: str = "",
    ):
        super().__init__(channel, uid=uid, name=name)
        self.loader = loader
        self.row = row or (lambda it: f"<li>{esc(str(it))}</li>")
        self.per_page = per_page
        self.empty_text = empty_text
        self.path_prefix = path_prefix


    def render(self, **state: Any) -> str:
        q = str(state.get("q", "") or "")
        page = max(1, int(state.get("page", 1) or 1))
        items: Sequence[Any] = state.get("items") or []
        total = int(state.get("total", len(items)) or 0)
        if self.loader and "items" not in state:
            items, total = self.loader(q, page, self.per_page)
        pages = max(1, (total + self.per_page - 1) // self.per_page) if total else 1

        search_btn = _button(self.ch, 
            "Search",
            self.action_name("search"),
            args={"q": q, "page": 1},
            target=self.uid,
        )
        search = (
            f'<div class="ux-list-search" style="display:flex;gap:.5rem;margin-bottom:.75rem">'
            f'<input id="{esc(self.uid)}-q" name="q" value="{esc(q)}" placeholder="Search…" '
            f'style="flex:1;padding:.5rem"/>'
            f"{search_btn}</div>"
        )
        if not items:
            body = f'<p class="ux-list-empty">{esc(self.empty_text)}</p>'
        else:
            body = (
                "<ul class='ux-list-items' style='list-style:none;padding:0;margin:0'>"
                + "".join(self.row(it) for it in items)
                + "</ul>"
            )

        pager = []
        if page > 1:
            pager.append(
                _button(self.ch, 
                    "Prev",
                    self.action_name("page"),
                    args={"q": q, "page": page - 1},
                    target=self.uid,
                )
            )
        pager.append(f'<span style="padding:.25rem .5rem">Page {page}/{pages}</span>')
        if page < pages:
            pager.append(
                _button(self.ch, 
                    "Next",
                    self.action_name("page"),
                    args={"q": q, "page": page + 1},
                    target=self.uid,
                )
            )
        footer = (
            f'<div class="ux-list-pager" style="display:flex;gap:.5rem;margin-top:.75rem;'
            f'align-items:center">{"".join(pager)}</div>'
        )
        return self.wrap(search + body + footer, class_="ux-list")

    def _load(self, q: str, page: int) -> Result:
        items: Sequence[Any] = []
        total = 0
        if self.loader:
            items, total = self.loader(q, page, self.per_page)
        html = self.render(q=q, page=page, items=items, total=total)
        ops = []
        if self.path_prefix:
            ops.append(push_url(f"{self.path_prefix}?q={q}&page={page}"))
        b = self.ch.ui.region(self.uid, html)
        for op in ops:
            b.op(op)
        return b.ok()

    def _register(self) -> None:
        comp = self

        @self.ch.action(self.action_name("search"))
        def search(q: str = "", page: int = 1) -> Result:
            return comp._load(q, max(1, int(page or 1)))

        @self.ch.action(self.action_name("page"))
        def page(q: str = "", page: int = 1) -> Result:
            return comp._load(q, max(1, int(page or 1)))

        @self.ch.action(self.action_name("refresh"))
        def refresh(q: str = "", page: int = 1) -> Result:
            return comp._load(q, max(1, int(page or 1)))
