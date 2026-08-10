"""
ux-dom + uxchannel shop — real integration surface for brutal tests.

ux-dom owns documents and controls.
uxchannel owns: scripts, control, trust, regions, actions, caps.
"""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from ux_dom import Document
from ux_dom.dom import button, div, form, h1, h2, input_, label, p, raw, span

from ux_channel import Channel, ChannelConfig, Region
from ux_channel.demo import (
    attr_string,
    demo_button,
    demo_page,
    demo_scripts,
    script_tags,
)
from ux_channel.response import HTMLResponse as UidHTMLResponse

# --- app / channel ---------------------------------------------------------

app = FastAPI(title="ux_dom-shop")
SECRET = "ux_dom-shop-secret-key-32chars-min!!"
ch = Channel.boot(
    app,
    config=ChannelConfig.development(secret=SECRET, allow_memory_stores=True),
)

# In-memory "DB"
DB: dict[str, Any] = {
    "stock": {"sku-a": 100, "sku-b": 50, "sku-c": 25},
    "carts": {},  # user_id -> {sku: qty}
    "orders": [],
}


def _uid(ctx) -> str:
    if ctx is None:
        return "anon"
    return str(
        getattr(ctx, "subject", None)
        or getattr(ctx, "user_id", None)
        or (ctx.scope or {}).get("user_id")
        or "anon"
    )


def cart_for(user: str) -> dict[str, int]:
    return DB["carts"].setdefault(user, {})


# --- regions (class-style) -------------------------------------------------

class CartBadge(Region):
    def render(self, ctx):
        user = _uid(ctx)
        n = sum(cart_for(user).values())
        return span(f"Cart ({n})", className="badge", data_channel_id=self.uid)


class CartPanel(Region):
    def render(self, ctx):
        user = _uid(ctx)
        cart = cart_for(user)
        if not cart:
            return div(p("Empty cart"), data_channel_id=self.uid, className="panel")
        lines = [
            div(
                f"{sku} × {qty} ",
                button(
                    "−",
                    type="button",
                    **ch.control(remove_line, trust_sku=sku).as_ux_dom(),
                ),
                className="line",
            )
            for sku, qty in cart.items()
        ]
        return div(*lines, data_channel_id=self.uid, className="panel")


class FlashBar(Region):
    def render(self, ctx):
        user = _uid(ctx)
        data = ch.draft.get(f"flash:{user}") or {}
        msg = data.get("message") or ""
        level = data.get("level") or "info"
        return div(msg, className=f"flash {level}", data_channel_id=self.uid)


class Catalog(Region):
    def render(self, ctx):
        items = []
        for sku, stock in DB["stock"].items():
            items.append(
                div(
                    span(f"{sku} (stock {stock}) "),
                    button(
                        "Add",
                        type="button",
                        **ch.control(add_item, trust_sku=sku).as_ux_dom(),
                    ),
                    className="item",
                )
            )
        return div(h2("Catalog"), *items, data_channel_id=self.uid)


class CheckoutForm(Region):
    def render(self, ctx):
        err = (ch.draft.get(f"co_err:{_uid(ctx)}") or {})
        email = err.get("email_value") or ""
        msgs = err.get("fields") or {}
        email_err = (msgs.get("email") or [""])[0]
        return form(
            label("Email"),
            input_(name="email", value=email, id="email"),
            span(email_err, className="err") if email_err else "",
            button("Checkout", type="submit"),
            **ch.control(checkout).as_ux_dom(),
            data_channel_id=self.uid,
            className="checkout",
        )


class AdminRefunds(Region):
    def render(self, ctx):
        rows = [div(f"order {o['id']} {o['user']} ${o['total']}") for o in DB["orders"][-10:]]
        return div(
            h2("Refunds"),
            *rows,
            button(
                "Refund last",
                type="button",
                **ch.control(refund_last).as_ux_dom(),
            )
            if DB["orders"]
            else p("No orders"),
            data_channel_id=self.uid,
        )


badge = ch.use(CartBadge)
panel = ch.use(CartPanel)
flash = ch.use(FlashBar)
catalog = ch.use(Catalog)
checkout_ui = ch.use(CheckoutForm)
admin = ch.use(AdminRefunds)


def _flash(ctx, msg: str, level: str = "info") -> None:
    ch.draft.set(f"flash:{_uid(ctx)}", {"message": msg, "level": level})


# --- actions ---------------------------------------------------------------

@ch.on(refresh=[badge, panel, flash, catalog], auth=False)
def add_item(ctx=None, sku: str = ""):
    # principal from keys if test injects user_id
    user = _uid(ctx) if ctx is not None else "anon"
    if ctx is not None:
        user = _uid(ctx)
    stock = DB["stock"].get(sku, 0)
    if stock <= 0:
        if ctx is not None:
            _flash(ctx, "Out of stock", "error")
        return None
    cart = cart_for(user)
    cart[sku] = cart.get(sku, 0) + 1
    DB["stock"][sku] = stock - 1
    if ctx is not None:
        _flash(ctx, f"Added {sku}", "success")
    return None


# Register with explicit names matching Region methods for class mount...
# Class-style already registered CartBadge.add etc. We use free functions for seal args.

# Fix: re-bind as free functions used in Catalog.render - already @ch.on above.

@ch.on(refresh=[badge, panel, flash], auth=False)
def remove_line(ctx=None, sku: str = ""):
    user = _uid(ctx) if ctx is not None else "anon"
    cart = cart_for(user)
    if sku in cart:
        cart[sku] -= 1
        DB["stock"][sku] = DB["stock"].get(sku, 0) + 1
        if cart[sku] <= 0:
            del cart[sku]
        if ctx is not None:
            _flash(ctx, f"Removed {sku}", "info")
    return None


@ch.on(refresh=[badge, panel, flash, checkout_ui, catalog], auth=False)
def checkout(ctx=None, email: str = ""):
    user = _uid(ctx) if ctx is not None else "anon"
    email = (email or "").strip()
    if not email or "@" not in email:
        ch.draft.set(
            f"co_err:{user}",
            {"fields": {"email": ["Valid email required"]}, "email_value": email},
        )
        return ch.fail.valid(
            {"email": ["Valid email required"]},
            region=checkout_ui.uid,
            html=checkout_ui.html(user_id=user),
            focus="#email",
        )
    cart = cart_for(user)
    if not cart:
        if ctx is not None:
            _flash(ctx, "Cart empty", "error")
        return None
    total = sum(cart.values())  # qty as fake $
    oid = len(DB["orders"]) + 1
    DB["orders"].append({"id": oid, "user": user, "total": total, "email": email, "items": dict(cart)})
    DB["carts"][user] = {}
    ch.draft.set(f"co_err:{user}", {})
    if ctx is not None:
        _flash(ctx, f"Order #{oid} placed", "success")
    return None


@ch.on(refresh=[admin, flash], auth=True, once=True, roles=("admin",), audit=True)
def refund_last(ctx=None):
    if not DB["orders"]:
        if ctx is not None:
            _flash(ctx, "Nothing to refund", "warning")
        return None
    order = DB["orders"].pop()
    if ctx is not None:
        _flash(ctx, f"Refunded #{order['id']}", "success")
    return None


# Wire free functions' stamps for bind in Catalog (already have .action from @ch.on)

# --- document --------------------------------------------------------------

document = Document(
    head=[
        raw(str(demo_scripts(ch, ))),
        raw("<style>.badge{font-weight:bold}.flash.error{color:red}.flash.success{color:green}.err{color:red;font-size:12px}</style>"),
    ],
    body=[],
)


def page_for(user_id: str = "anon", *, admin_view: bool = False) -> Any:
    scope = {"user_id": user_id}
    # SSR regions with scope
    body = div(
        h1("ux-dom Shop"),
        raw(flash.html(**scope)),
        raw(badge.html(**scope)),
        raw(catalog.html(**scope)),
        raw(panel.html(**scope)),
        raw(checkout_ui.html(**scope)),
        raw(admin.html(**scope)) if admin_view else "",
        className="app",
        **{
            # body attrs for channel endpoint — Document may wrap; also set via page
        },
    )
    # HtmlDocument from document()
    return document(body, title="ux-dom Shop")


@app.get("/", response_class=HTMLResponse)
def index(request: Request):
    user = request.headers.get("x-user-id") or request.query_params.get("user") or "anon"
    admin_view = request.query_params.get("admin") == "1"
    tree = page_for(user, admin_view=admin_view)
    # ux_dom HTMLResponse-compatible: render tree
    html = tree.__render__() if hasattr(tree, "__render__") else str(tree)
    # ensure body has channel endpoint (document may not merge our body attrs)
    if "data-channel-endpoint" not in html:
        html = html.replace("<body", f"<body {attr_string(ch.body_attrs())}", 1)
    return HTMLResponse(html)


@app.get("/health")
def health():
    return {"ok": True, "orders": len(DB["orders"]), "stock": DB["stock"]}


def reset_db():
    DB["stock"] = {"sku-a": 100, "sku-b": 50, "sku-c": 25}
    DB["carts"] = {}
    DB["orders"] = []
    # clear draft-ish via new channel state is hard; draft is on ch.state
    if hasattr(ch, "state") and hasattr(ch.state, "clear"):
        try:
            ch.state.clear()
        except Exception:
            pass


# expose for tests
app.state.ch = ch
app.state.DB = DB
app.state.reset_db = reset_db
app.state.page_for = page_for
app.state.SECRET = SECRET
