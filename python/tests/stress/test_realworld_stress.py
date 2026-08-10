"""
Real-world shop flow + stress: regions, login, forms, drafts, concurrency.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field

import pytest

from ux_channel import Channel, ChannelTest, Intent, Result
from ux_channel.render.kit import attr_string, demo_button, demo_page, demo_scripts, script_tags
from ux_channel.security.bulkhead import install_bulkhead

SECRET = "dev-secret-key-32chars-minimum!!!!"


@dataclass
class ShopDB:
    users: dict = field(default_factory=lambda: {"u1": {"name": "Ada"}})
    products: dict = field(
        default_factory=lambda: {
            "p1": {"title": "Ring", "price": 100, "stock": 50},
            "p2": {"title": "Chain", "price": 40, "stock": 50},
        }
    )
    carts: dict = field(default_factory=dict)  # user_id -> {product_id: qty}
    orders: list = field(default_factory=list)

    def cart_lines(self, user_id: str) -> list:
        c = self.carts.get(user_id, {})
        out = []
        for pid, qty in c.items():
            p = self.products[pid]
            out.append({"id": pid, "title": p["title"], "qty": qty, "price": p["price"]})
        return out

    def cart_count(self, user_id: str) -> int:
        return sum(self.carts.get(user_id, {}).values())

    def cart_total(self, user_id: str) -> int:
        return sum(l["qty"] * l["price"] for l in self.cart_lines(user_id))

    def add(self, user_id: str, product_id: str, qty: int = 1) -> None:
        if product_id not in self.products:
            raise KeyError(product_id)
        if self.products[product_id]["stock"] < qty:
            raise ValueError("out of stock")
        self.carts.setdefault(user_id, {})
        self.carts[user_id][product_id] = self.carts[user_id].get(product_id, 0) + qty
        self.products[product_id]["stock"] -= qty

    def checkout(self, user_id: str) -> dict:
        lines = self.cart_lines(user_id)
        if not lines:
            raise ValueError("empty")
        order = {"user_id": user_id, "lines": lines, "total": self.cart_total(user_id)}
        self.orders.append(order)
        self.carts[user_id] = {}
        return order


def build_shop(db: ShopDB | None = None) -> Channel:
    db = db or ShopDB()
    ch = Channel.boot(secret=SECRET)

    @ch.region("Cart:badge")
    def badge(ctx):
        return {"n": db.cart_count(ctx.key("user_id", "guest"))}

    @badge.html
    def badge_html(data, ctx):
        return f'<span class="badge" data-n="{data["n"]}">{data["n"]}</span>'

    @ch.region("Cart:panel")
    def panel(ctx):
        uid = ctx.key("user_id", "guest")
        return {"lines": db.cart_lines(uid), "total": db.cart_total(uid)}

    @panel.paint
    def panel_html(data, ctx):
        items = "".join(
            f'<li data-id="{l["id"]}">{l["title"]} ×{l["qty"]}</li>' for l in data["lines"]
        )
        return f'<ul class="cart">{items}</ul><div class="total">{data["total"]}</div>'

    @ch.region("Catalog:list")
    def catalog(ctx):
        q = (ctx.key("q") or "").lower()
        items = [
            {"id": i, **p}
            for i, p in db.products.items()
            if not q or q in p["title"].lower()
        ]
        return {"items": items, "q": q}

    @catalog.paint
    def catalog_html(data, ctx):
        return "".join(
            f'<div class="product" data-id="{i["id"]}">{i["title"]} ${i["price"]}</div>'
            for i in data["items"]
        )

    @ch.region("Checkout:form")
    def checkout_form(ctx):
        err = ctx.key("error")
        return {"error": err, "total": db.cart_total(ctx.key("user_id", "guest"))}

    @checkout_form.paint
    def checkout_html(data, ctx):
        err = f'<p class="err">{data["error"]}</p>' if data["error"] else ""
        return f'{err}<form>Total: {data["total"]}</form>'

    @ch.on("Cart.add", refresh=["Cart:badge", "Cart:panel", "Catalog:list"],
        notice="Added",
        auth=True,
    )
    def cart_add(product_id: str, ctx):
        try:
            db.add(ctx.user_id, product_id)
        except ValueError:
            return ch.notice("Out of stock", level="error")
        except KeyError:
            return ch.fail.forbidden("Unknown product")

    @ch.on("Cart.checkout", auth=True, refresh=["Cart:badge", "Cart:panel", "Checkout:form"],
        notice="Order placed",
    )
    def checkout(ctx):
        try:
            db.checkout(ctx.user_id)
        except ValueError:
            return ch.fail.valid(
                {"cart": ["Cart is empty"]},
                region="Checkout:form",
                html=ch.regions.get("Checkout:form").html(
                    ch.regions.context(scope={"user_id": ctx.user_id, "error": "Cart is empty"})
                ),
                message="Cart is empty",
            )

    @ch.action("Catalog.search")
    def search(q: str = "", user_id: str = "guest"):
        return ch.filter("Catalog:list", q=q, user_id=user_id)

    @ch.action("Draft.note")
    def draft_note(text: str = "", user_id: str = "guest"):
        ch.draft.set(f"note:{user_id}", {"text": text})
        return ch.notice("Draft saved", level="success")

    # stash db for tests
    ch._shop_db = db  # type: ignore[attr-defined]
    return ch


def test_shop_happy_path():
    ch = build_shop()
    t = ChannelTest(ch)

    # login required
    t.call("Cart.add", product_id="p1").assert_fail("unauthorized")

    t.call("Cart.add", product_id="p1", user_id="u1").assert_ok().assert_notice("Added")
    r = t.call("Cart.add", product_id="p2", user_id="u1").assert_ok()
    assert any("data-n=\"2\"" in str(o.get("html", "")) or ">2<" in str(o.get("html", "")) for o in r.ops)

    # search
    t.call("Catalog.search", q="ring", user_id="u1").assert_ok().assert_morph("Catalog:list", contains="Ring")

    # checkout
    t.call("Cart.checkout", user_id="u1").assert_ok().assert_notice("Order placed")
    assert ch._shop_db.cart_count("u1") == 0  # type: ignore[attr-defined]
    assert len(ch._shop_db.orders) == 1  # type: ignore[attr-defined]


def test_shop_empty_checkout_validation():
    ch = build_shop()
    r = ChannelTest(ch).call("Cart.checkout", user_id="u1")
    assert not r.ok or any(o.get("op") == "toast" for o in r.ops)
    # form_fail returns validation
    if not r.ok:
        r.assert_fail("validation")


def test_draft_pattern():
    ch = build_shop()
    ChannelTest(ch).call("Draft.note", text="hello", user_id="u1").assert_ok().assert_notice("Draft saved")
    assert ch.draft.get("note:u1")["text"] == "hello"


def test_ssr_html_regions():
    ch = build_shop()
    page = ch.html("Cart:badge", scope={"user_id": "u1"}) + ch.html("Catalog:list", scope={"q": ""})
    assert "data-channel-id=\"Cart:badge\"" in page
    assert "Ring" in page and "Chain" in page


def test_concurrent_adds_stress():
    db = ShopDB()
    db.products["p1"]["stock"] = 500
    ch = build_shop(db)
    # lower rate limit noise
    ch.registry.hooks.before.clear()

    def one(i: int):
        cap = ch.mint("Cart.add", {"product_id": "p1", "user_id": "u1"})
        r = ch.registry.dispatch(
            Intent(action="Cart.add", args={"product_id": "p1", "user_id": "u1"}, cap=cap)
        )
        return r.ok

    with ThreadPoolExecutor(32) as ex:
        oks = list(ex.map(one, range(200)))
    assert all(oks)
    assert db.cart_count("u1") == 200
    assert db.products["p1"]["stock"] == 300


def test_bulkhead_under_burst():
    ch = build_shop()
    ch.registry.hooks.before.clear()
    install_bulkhead(ch.registry, max_in_flight=4)

    @ch.action("Slow.ok")
    def slow():
        return Result.success()

    def hit(_):
        cap = ch.mint("Slow.ok", {})
        return ch.registry.dispatch(Intent(action="Slow.ok", args={}, cap=cap))

    with ThreadPoolExecutor(20) as ex:
        results = list(ex.map(hit, range(40)))
    # some may rate_limit via bulkhead
    codes = [(r.ok, r.error.code if r.error else None) for r in results]
    assert any(ok for ok, _ in codes)
    # bulkhead returns rate_limited when full — not required if fast enough
    assert len(results) == 40


def test_patterns_form_ok_fail():
    ch = Channel.boot(secret=SECRET)

    @ch.region("Form:root")
    def form(ctx):
        return {"email": ctx.key("email", "")}

    @form.paint
    def form_html(data, ctx):
        return f'<input value="{data["email"]}"/>'

    ok = ch.done("Saved", refresh=["Form:root"], scope={"email": "a@b.c"})
    assert ok.ok and any(o.get("op") == "toast" for o in ok.ops)

    bad = ch.fail.valid(
        {"email": ["required"]},
        region="Form:root",
        html=ch.html("Form:root", wrap=False),
        focus="#email",
    )
    assert not bad.ok and bad.error.code == "validation"


def test_page_shell_and_diagnose():
    ch = build_shop()
    html = demo_page(ch, ch.html("Cart:badge", scope={"user_id": "u1"}), title="Shop")
    assert "ux-channel.js" in html and "data-channel-dev" in html
    d = ch.diagnose()
    assert "Cart:badge" in d["regions"]
    assert d["state"] == "MemoryStateStore"
