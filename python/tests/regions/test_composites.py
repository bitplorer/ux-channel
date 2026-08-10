"""Composition layer + complex composites (UxDom-like fragments)."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from ux_channel import Channel, ChannelConfig, Result
from ux_channel.demo import attr_string, demo_button, demo_page, demo_scripts, script_tags
from ux_channel.components import (
    AppShell,
    CartPanel,
    Composite,
    Dashboard,
    DataTable,
    Block,
    LoginCard,
    MediaCard,
    RegistryHost,
    fragment,
    plug,
    stamp_attrs,
    to_html,
)
from ux_channel.types import Intent

SECRET = "dev-secret-key-32chars-minimum!!!!"


def _ch(app=None):
    cfg = ChannelConfig.development(
        secret=SECRET, rate_limit_per_minute=0, require_channel_header=False
    )
    return Channel.boot(app, config=cfg)


class UxDomNode:
    """Duck-typed stand-in for UxDom Component / dom_tag."""

    def __init__(self, html: str):
        self._html = html

    def __render__(self):
        return self._html


def test_fragment_and_to_html_ux_dom():
    node = UxDomNode("<span class='u'>ring</span>")
    assert "ring" in fragment(node)
    assert to_html(node) == node.__render__()


def test_island_swap_foreign_body():
    ch = _ch()
    island = Block(ch, uid="Hero:root", body=UxDomNode("<h1>Hi</h1>")).install()
    html = island.render()
    assert "Hero:root" in html and "Hi" in html
    r = island.swap(UxDomNode("<h1>Bye</h1>"), notice="updated")
    assert r.ok and "Bye" in r.ops[0]["html"]


def test_plug_one_liner():
    ch = _ch()
    i = plug(ch, "Plug:root", UxDomNode("<p>x</p>"))
    assert i._installed and "x" in i.render()


def test_stamp_attrs_on_foreign_button():
    raw = '<button type="button" class="btn">Go</button>'
    out = stamp_attrs(raw, action="X.go", trust={"a": 1}, cap="cap123")
    assert "data-channel-action=" in out and "cap123" in out and "Go" in out


def test_composite_slots_with_channel_and_ux_dom():
    ch = _ch()

    class Card(Composite):
        kind = "Card"
        slot_names = ("media", "body")

        def layout(self, slots, **state):
            return f"{slots['media']}<div>{slots['body']}</div>"

    card = Card(
        ch,
        uid="Card:1",
        slots={
            "media": UxDomNode("<img alt='x'/>"),
            "body": "<p>hello</p>",
        },
    ).install()
    html = card.render()
    assert "img" in html and "hello" in html and "Card:1" in html


def test_app_shell_with_nested_island():
    ch = _ch()
    main = Block(ch, uid="Main:root", body="<p>content</p>").install()
    shell = AppShell(
        ch,
        uid="App:shell",
        slots={
            "brand": UxDomNode("<strong>Shop</strong>"),
            "nav": "<a href='/'>Home</a>",
            "main": main,
            "footer": "© 2026",
        },
    ).install()
    html = shell.render()
    assert "Shop" in html and "content" in html and "© 2026" in html


def test_login_card_validation():
    ch = _ch()
    card = LoginCard(
        ch,
        uid="Auth:card",
        validate=lambda v: {"email": ["bad"]} if "@" not in v.get("email", "") else {},
        success_redirect="/app",
        slots={"title": UxDomNode("<h2>Welcome</h2>")},
    ).install()
    assert "Welcome" in card.render()
    r = ch.registry.dispatch(
        Intent(
            action="LoginCardForm.submit",
            form={"email": "x", "password": "password1"},
            cap=ch.mint("LoginCardForm.submit", {}),
        )
    )
    assert not r.ok


def test_cart_panel_checkout():
    ch = _ch()
    got = {}

    def checkout(lines):
        got["lines"] = lines
        return Result.success()

    cart = CartPanel(ch, uid="Cart:panel", on_checkout=checkout).install()
    html = cart.render(lines=[{"title": "Ring", "qty": 2}])
    assert "Ring" in html and "Items" in html
    r = ch.registry.dispatch(
        Intent(
            action="Cart.checkout",
            args={"n": 2},
            cap=ch.mint("Cart.checkout", {"n": 2}),
        )
    )
    assert r.ok
    assert got.get("lines")


def test_data_table_sort_page():
    ch = _ch()
    rows_all = [{"id": i, "name": f"P{i}"} for i in range(15)]

    def loader(q, sort, desc, page, per_page):
        data = [r for r in rows_all if q in r["name"]] if q else list(rows_all)
        data.sort(key=lambda r: r[sort], reverse=desc)
        s = (page - 1) * per_page
        return data[s : s + per_page], len(data)

    table = DataTable(
        ch,
        uid="T:root",
        columns=("id", "name"),
        loader=loader,
        row_cells=lambda r: [r["id"], UxDomNode(f"<b>{r['name']}</b>")],
        per_page=5,
    ).install()
    html = table.render(page=1, rows=rows_all[:5], total=15, sort="id", desc=False)
    assert "P0" in html
    r = ch.registry.dispatch(
        Intent(
            action="DataTable.page",
            args={"q": "", "sort": "id", "desc": False, "page": 2},
            cap=ch.mint(
                "DataTable.page", {"q": "", "sort": "id", "desc": False, "page": 2}
            ),
        )
    )
    assert r.ok and "P5" in r.ops[0]["html"]


def test_dashboard_and_media_card():
    ch = _ch()
    table = DataTable(
        ch,
        uid="Dash:table",
        name="Sales",
        columns=("id", "name"),
        loader=lambda q, s, d, p, pp: ([{"id": 1, "name": "A"}], 1),
    ).install()
    dash = Dashboard(
        ch,
        uid="Dash:root",
        panels={"sales": table, "note": UxDomNode("<p>hello</p>")},
    ).install()
    assert "Sales" in dash.render() and "hello" in dash.render()

    card = MediaCard(
        ch,
        uid="M:1",
        primary_action="MediaCard.noop",
        slots={
            "media": UxDomNode("<img src='x'/>"),
            "title": "Gold Ring",
            "body": "22k",
            "meta": "$100",
        },
    ).install()
    # register noop
    ch.register("MediaCard.noop", lambda: Result.success())
    assert "Gold Ring" in card.render()


def test_registry_host_composites():
    from ux_channel import ActionRegistry

    reg = ActionRegistry(secret=SECRET, require_cap=True)
    host = RegistryHost(reg)
    island = Block(host, uid="I:1", body=UxDomNode("<i>z</i>")).install()
    assert "z" in island.render()


def test_http_shell_demo_smoke():
    app = FastAPI()
    ch = _ch(app)
    cart = CartPanel(ch, uid="Cart:panel").install()
    shell = AppShell(
        ch,
        slots={
            "brand": "Demo",
            "main": cart,
            "flash": "",
        },
    ).install()

    @app.get("/")
    def index():
        return demo_page(ch, shell.render(lines=[]), title="composites")

    c = TestClient(app)
    assert c.get("/").status_code == 200
    assert "Cart" in c.get("/").text or "uid-cart" in c.get("/").text or "Checkout" in c.get("/").text
