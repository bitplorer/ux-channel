"""
Enterprise real-world + brutal stress / pen tests for uxchannel 2.x.
"""

from __future__ import annotations

import json
import threading
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from ux_channel import Channel, ChannelConfig, Intent, Result
from ux_channel.host.testing import ChannelTest
from ux_channel.security.bulkhead import install_bulkhead
from ux_channel.protocol.capability import CapError
from ux_channel.host.nonce import MemoryNonceStore

SECRET = "ent-secret-key-32chars-minimum!!!!!!"


# ---------------------------------------------------------------------------
# Multi-tenant commerce domain
# ---------------------------------------------------------------------------


@dataclass
class EntDB:
    tenants: dict = field(default_factory=lambda: {"t1": {}, "t2": {}})
    # tenant -> user -> roles
    users: dict = field(
        default_factory=lambda: {
            "t1": {"alice": {"roles": ["buyer"]}, "bob": {"roles": ["admin", "finance"]}},
            "t2": {"carol": {"roles": ["buyer"]}},
        }
    )
    # tenant -> product_id -> stock/price
    catalog: dict = field(
        default_factory=lambda: {
            "t1": {"sku1": {"title": "Gold Ring", "stock": 100, "price": 500}},
            "t2": {"sku9": {"title": "Other", "stock": 10, "price": 9}},
        }
    )
    carts: dict = field(default_factory=dict)  # (tenant, user) -> {sku: qty}
    refunds: list = field(default_factory=list)
    lock: threading.RLock = field(default_factory=threading.RLock)

    def add_cart(self, tenant: str, user: str, sku: str, qty: int = 1) -> None:
        with self.lock:
            if sku not in self.catalog.get(tenant, {}):
                raise KeyError("sku")
            if self.catalog[tenant][sku]["stock"] < qty:
                raise ValueError("stock")
            key = (tenant, user)
            self.carts.setdefault(key, {})
            self.carts[key][sku] = self.carts[key].get(sku, 0) + qty
            self.catalog[tenant][sku]["stock"] -= qty

    def cart_count(self, tenant: str, user: str) -> int:
        with self.lock:
            return sum(self.carts.get((tenant, user), {}).values())

    def refund(self, tenant: str, order_id: str, actor: str) -> None:
        with self.lock:
            self.refunds.append({"tenant": tenant, "order_id": order_id, "actor": actor})


def build_enterprise(db: EntDB | None = None) -> Channel:
    db = db or EntDB()
    ch = Channel.boot(secret=SECRET)

    @ch.region("Cart:badge")
    def badge(ctx):
        return {
            "n": db.cart_count(ctx.key("tenant_id", "t1"), ctx.key("user_id", "guest"))
        }

    @badge.html
    def badge_html(data, ctx):
        return f'<span class="badge">{data["n"]}</span>'

    @ch.region("Admin:refunds")
    def refunds(ctx):
        tenant = ctx.key("tenant_id", "t1")
        rows = [r for r in db.refunds if r["tenant"] == tenant]
        page = ch.paginate(rows, page=int(ctx.key("page", 1) or 1), per_page=10)
        return page

    @refunds.paint
    def refunds_html(data, ctx):
        items = "".join(f'<li>{r["order_id"]}</li>' for r in data["items"])
        return f'<ul data-page="{data["page"]}">{items}</ul>'

    @ch.on(
        "Cart.add",
        refresh=["Cart:badge"],
        auth=True,
        notice="Added",
    )
    def cart_add(sku: str, ctx):
        tenant = ctx.key("tenant_id", "t1")
        try:
            db.add_cart(tenant, ctx.user_id, sku)
        except KeyError:
            return ch.fail.forbidden("unknown sku")
        except ValueError:
            return ch.notice("Out of stock", level="error")

    @ch.on(
        "Order.refund",
        refresh=["Admin:refunds"],
        auth=True,
        once=True,
        roles=["admin", "finance"],
        audit=True,
        notice="Refunded",
    )
    def refund(order_id: str, ctx):
        tenant = ctx.key("tenant_id", "t1")
        # tenant isolation: never refund other tenant's implied data without key
        db.refund(tenant, order_id, actor=str(ctx.user_id))
        return ch.done("Refunded")

    @ch.on("Catalog.page", refresh=["Admin:refunds"])
    def catalog_page(page: int = 1, ctx=None):
        return ch.done(refresh=["Admin:refunds"], scope={"page": page, "tenant_id": (ctx.scope.get("tenant_id") if ctx else "t1")})

    ch._db = db  # type: ignore[attr-defined]
    return ch


# ---------------------------------------------------------------------------
# Functional enterprise cases
# ---------------------------------------------------------------------------


def test_tenant_cart_happy_path():
    ch = build_enterprise()
    t = ChannelTest(ch)
    t.call("Cart.add", sku="sku1").assert_fail("unauthorized")
    t.call(
        "Cart.add", sku="sku1", user_id="alice", tenant_id="t1"
    ).assert_ok().assert_notice("Added")
    assert ch._db.cart_count("t1", "alice") == 1  # type: ignore[attr-defined]
    # cannot add other tenant sku
    r = t.call("Cart.add", sku="sku9", user_id="alice", tenant_id="t1")
    assert not r.ok or r.result.error  # forbidden


def test_role_gate_refund():
    ch = build_enterprise()
    t = ChannelTest(ch)
    # buyer lacks role
    t.call(
        "Order.refund",
        order_id="o1",
        user_id="alice",
        tenant_id="t1",
        roles=["buyer"],
    ).assert_fail("forbidden")
    # admin ok
    t.call(
        "Order.refund",
        order_id="o1",
        user_id="bob",
        tenant_id="t1",
        roles=["admin"],
    ).assert_ok().assert_notice("Refunded")
    assert len(ch.audit_log.list(action="Order.refund")) >= 1


def test_once_cap_replay_blocked():
    ch = build_enterprise()
    assert ch.registry.nonce_store is not None
    args = {"order_id": "o2", "user_id": "bob", "tenant_id": "t1", "roles": ["finance"]}
    cap = ch.mint("Order.refund", args, once=True)
    r1 = ch.registry.dispatch(Intent(action="Order.refund", args=args, cap=cap))
    assert r1.ok, r1.error
    r2 = ch.registry.dispatch(Intent(action="Order.refund", args=args, cap=cap))
    assert not r2.ok
    assert r2.error and "replay" in (r2.error.message or "").lower() or r2.error.code in (
        "unauthorized",
        "forbidden",
        "bad_request",
    )


def test_auto_once_on_sign_from_policy():
    ch = build_enterprise()
    # policy once=True should inject once into sign
    cap = ch.mint("Order.refund", {"order_id": "x", "user_id": "bob"})
    # decode via second use - if once, second fails
    args = {"order_id": "x", "user_id": "bob", "tenant_id": "t1", "roles": ["admin"]}
    # resign with same policy
    cap = ch.mint("Order.refund", args)
    r1 = ch.registry.dispatch(Intent(action="Order.refund", args=args, cap=cap))
    r2 = ch.registry.dispatch(Intent(action="Order.refund", args=args, cap=cap))
    assert r1.ok and not r2.ok


def test_pagination_island():
    ch = build_enterprise()
    db: EntDB = ch._db  # type: ignore[attr-defined]
    for i in range(25):
        db.refund("t1", f"ord-{i}", "bob")
    html = ch.html("Admin:refunds", scope={"tenant_id": "t1", "page": 1})
    assert "data-page=\"1\"" in html
    r = ch.refresh("Admin:refunds", scope={"tenant_id": "t1", "page": 2})
    assert r.ok and any("data-page=\"2\"" in str(o.get("html", "")) for o in r.ops)


# ---------------------------------------------------------------------------
# HTTP pen / CSRF / origin
# ---------------------------------------------------------------------------


def test_http_pen_missing_channel_header():
    app = FastAPI()
    cfg = ChannelConfig.production(SECRET, allow_memory_stores=True, rate_limit_per_minute=0)
    ch = Channel.boot(app, config=cfg)
    # re-bind enterprise after boot with production config
    from ux_channel.devtools.enterprise import attach_enterprise
    attach_enterprise(ch)

    @ch.on("Ping.x")
    def ping():
        return ch.done("p")

    client = TestClient(app)
    # production requires X-Channel
    r = client.post(
        "/ux-channel/action",
        json={"v": "1", "action": "Ping.x", "args": {}},
        headers={"content-type": "application/json"},
    )
    assert r.status_code in (403, 401, 422)


def test_http_forged_cap_rejected():
    app = FastAPI()
    cfg = ChannelConfig.development(SECRET, require_channel_header=False, rate_limit_per_minute=0)
    ch = Channel.boot(app, config=cfg)

    @ch.on("Ping.x")
    def ping():
        return ch.done("p")

    client = TestClient(app)
    r = client.post(
        "/ux-channel/action",
        json={
            "v": "1",
            "action": "Ping.x",
            "args": {},
            "cap": "forged.not.a.real.cap",
        },
        headers={"content-type": "application/json", "X-Channel": "1"},
    )
    assert r.status_code >= 400 or r.json().get("ok") is False


def test_xss_user_content_escaped():
    from ux_channel.render.html_safe import esc, user_content

    evil = '<script>alert(1)</script>'
    assert "<script>" not in esc(evil)
    assert "<script>" not in user_content(evil)


# ---------------------------------------------------------------------------
# Stress / load
# ---------------------------------------------------------------------------


def test_stress_concurrent_cart_adds():
    db = EntDB()
    db.catalog["t1"]["sku1"]["stock"] = 5000
    ch = build_enterprise(db)
    ch.registry.hooks.before.clear()

    def one(i: int) -> bool:
        args = {"sku": "sku1", "user_id": "alice", "tenant_id": "t1"}
        cap = ch.mint("Cart.add", args)
        r = ch.registry.dispatch(Intent(action="Cart.add", args=args, cap=cap))
        return r.ok

    with ThreadPoolExecutor(48) as ex:
        oks = list(ex.map(one, range(1000)))
    assert all(oks)
    assert db.cart_count("t1", "alice") == 1000
    assert db.catalog["t1"]["sku1"]["stock"] == 4000


def test_stress_once_caps_no_double_refund():
    ch = build_enterprise()
    ch.registry.hooks.before.clear()
    args = {"order_id": "once-1", "user_id": "bob", "tenant_id": "t1", "roles": ["finance"]}
    # each thread gets own once cap
    def one(i: int) -> str:
        a = {**args, "order_id": f"once-{i}"}
        cap = ch.mint("Order.refund", a)  # policy once
        r1 = ch.registry.dispatch(Intent(action="Order.refund", args=a, cap=cap))
        r2 = ch.registry.dispatch(Intent(action="Order.refund", args=a, cap=cap))
        return f"{r1.ok}:{r2.ok}"

    with ThreadPoolExecutor(32) as ex:
        results = list(ex.map(one, range(100)))
    assert all(r == "True:False" for r in results)
    assert len(ch._db.refunds) == 100  # type: ignore[attr-defined]


def test_bulkhead_load():
    ch = Channel.boot(secret=SECRET)
    ch.registry.hooks.before.clear()
    install_bulkhead(ch.registry, max_in_flight=8)

    @ch.on("Work.x")
    def work():
        return Result.success()

    def hit(_):
        cap = ch.mint("Work.x", {})
        return ch.registry.dispatch(Intent(action="Work.x", args={}, cap=cap))

    with ThreadPoolExecutor(40) as ex:
        out = list(ex.map(hit, range(200)))
    assert any(r.ok for r in out)
    assert len(out) == 200


def test_surface_still_clean():
    ch = Channel.boot(secret=SECRET)
    for legacy in ("island", "command", "revalidate", "fail_auth", "form_ok"):
        assert not hasattr(ch, legacy)
    assert hasattr(ch, "audit") and hasattr(ch, "paginate") and hasattr(ch, "policies")
