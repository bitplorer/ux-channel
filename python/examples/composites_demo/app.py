"""
Complex composites + ux-dom-like slots demo.

  uvicorn examples.composites_demo.app:app --reload --host 0.0.0.0 --port 8080

Shows AppShell, CartPanel, DataTable, MediaCard, Dashboard with duck-typed
\"ux-dom\" nodes (__render__) — no ux_dom package required.
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.responses import HTMLResponse

from ux_channel import Channel, Result
from ux_channel.paint.demo import (
    attr_string,
    demo_button,
    demo_page,
    demo_scripts,
    script_tags,
)
from ux_channel.components import (
    AppShell,
    Block,
    CartPanel,
    Dashboard,
    DataTable,
    MediaCard,
)

app = FastAPI(title="uxchannel composites")
ch = Channel.boot(app, secret="dev-secret-key-32chars-minimum!!!!")


class ux-dom:
    """Stand-in for ux_dom Component / tag trees."""

    def __init__(self, html: str):
        self.html = html

    def __render__(self):
        return self.html


PRODUCTS = [
    {"id": i, "name": f"Product {i}", "price": 10 * i}
    for i in range(1, 21)
]


def table_loader(q, sort, desc, page, per_page):
    data = [p for p in PRODUCTS if q.lower() in p["name"].lower()] if q else list(PRODUCTS)
    data.sort(key=lambda r: r.get(sort, r["id"]), reverse=bool(desc))
    start = (page - 1) * per_page
    return data[start : start + per_page], len(data)


table = DataTable(
    ch,
    uid="Shop:table",
    name="ShopTable",
    columns=("id", "name", "price"),
    loader=table_loader,
    row_cells=lambda r: [
        r["id"],
        ux-dom(f"<strong>{r['name']}</strong>"),
        f"${r['price']}",
    ],
    per_page=5,
    row_actions=lambda r: demo_button(ch, 
        "Add",
        "Shop.add",
        trust={"id": r["id"], "name": r["name"]},
        target="Cart:panel",
    ),
).install()

CART: list[dict] = []


def on_checkout(lines):
    CART.clear()
    return ch.patch(
        {
            "Cart:panel": cart.render(lines=[]),
            "Hero:root": hero.render(body=ux-dom("<p>Thanks for your order!</p>")),
        },
        notice="Order placed",
    )


cart = CartPanel(
    ch,
    uid="Cart:panel",
    on_checkout=on_checkout,
    line_renderer=lambda line: ux-dom(
        f"<li style='padding:.35rem 0'>{line.get('title')} × {line.get('qty', 1)}</li>"
    ),
    slots={"header": ux-dom("<strong>Your cart</strong>")},
).install()

hero = Block(
    ch,
    uid="Hero:root",
    body=ux-dom("<p style='color:#64748b'>Server-driven cart · ux-dom-like media slots</p>"),
).install()

card = MediaCard(
    ch,
    uid="Feature:card",
    name="Feature",
    primary_action="Shop.add",
    primary_label="Add featured",
    primary_args={"id": 1, "name": "Product 1"},
    slots={
        "media": ux-dom(
            "<div style='height:100px;background:linear-gradient(135deg,#fbbf24,#f59e0b)'></div>"
        ),
        "title": "Featured product",
        "body": "Channel MediaCard + foreign media slot",
        "meta": "$10",
    },
).install()

dash = Dashboard(
    ch,
    uid="Dash:root",
    title="Store",
    panels={
        "catalog": table,
        "featured": card,
    },
).install()

shell = AppShell(
    ch,
    uid="App:shell",
    slots={
        "brand": ux-dom("<span style='font-weight:700'>uxchannel shop</span>"),
        "nav": "<a href='/' style='color:#2563eb;text-decoration:none'>Home</a>",
        "main": dash,
        "sidebar": cart,
        "footer": ux-dom("<span>Composites layer · plug any library via to_html / __render__</span>"),
    },
).install()


@ch.action("Shop.add")
def add(id: int = 0, name: str = ""):
    # merge into cart lines
    for line in CART:
        if line.get("id") == id:
            line["qty"] = int(line.get("qty", 1)) + 1
            break
    else:
        CART.append({"id": id, "title": name or f"#{id}", "qty": 1})
    return cart.refresh(lines=list(CART), notice=f"Added {name or id}")


@app.get("/", response_class=HTMLResponse)
def index():
    body = f"""
<style>
  body {{ font-family: system-ui, sans-serif; max-width: 56rem; margin: 1.5rem auto; padding: 0 1rem; color: #0f172a; }}
  a {{ color: #2563eb; }}
  button {{ cursor: pointer; }}
</style>
{hero.render()}
{shell.render()}
"""
    return demo_page(ch, body, title="Composites demo", dev=True, inspector=True)
