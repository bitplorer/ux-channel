"""Region load / revalidate / command — lean DB→client flow."""

from __future__ import annotations

from ux_channel import Channel, Result
from ux_channel.host.testing import ChannelTest

SECRET = "dev-secret-key-32chars-minimum!!!!"


class FakeDB:
    def __init__(self):
        self.cart = {"u1": ["a"]}

    def count(self, user_id):
        return len(self.cart.get(user_id, []))

    def lines(self, user_id):
        return list(self.cart.get(user_id, []))

    def add(self, user_id, product_id):
        self.cart.setdefault(user_id, []).append(product_id)


def test_island_html_and_revalidate():
    db = FakeDB()
    ch = Channel.boot(secret=SECRET)

    @ch.region("Cart:badge")
    def badge(ctx):
        return {"n": db.count(ctx.user_id or ctx.key("user_id"))}

    @badge.html
    def badge_html(data, ctx):
        return f'<span class="n">{data["n"]}</span>'

    @ch.region("Cart:panel")
    def panel(ctx):
        return {"lines": db.lines(ctx.user_id or ctx.key("user_id"))}

    @panel.paint
    def panel_html(data, ctx):
        return "<ul>" + "".join(f"<li>{x}</li>" for x in data["lines"]) + "</ul>"

    html = ch.html("Cart:badge", scope={"user_id": "u1"})
    assert 'data-channel-id="Cart:badge"' in html and ">1<" in html

    db.add("u1", "b")
    r = ch.refresh("Cart:badge", "Cart:panel", scope={"user_id": "u1"}, notice="ok")
    assert r.ok
    ops = [o["op"] for o in r.ops]
    assert ops.count("morph") == 2
    assert any(o.get("op") == "toast" for o in r.ops)


def test_command_auto_revalidate():
    db = FakeDB()
    ch = Channel.boot(secret=SECRET)

    @ch.region("Cart:badge")
    def badge(ctx):
        return {"n": db.count(ctx.scope.get("user_id", "u1"))}

    @badge.html
    def badge_html(data, ctx):
        return f"<b>{data['n']}</b>"

    @ch.on("Cart.add", refresh=["Cart:badge"], notice="Added")
    def add(product_id: str, ctx):
        uid = ctx.key("user_id", "u1")
        db.add(uid, product_id)

    # sign/call with user_id as arg → becomes key
    (
        ChannelTest(ch)
        .call("Cart.add", product_id="z", user_id="u1")
        .assert_ok()
        .assert_morph("Cart:badge", contains="2")
        .assert_notice("Added")
    )


def test_etag_skips_unchanged():
    ch = Channel.boot(secret=SECRET)
    store = {"v": 1}

    @ch.region("X:root", etag=lambda data, ctx: str(data["v"]))
    def x(ctx):
        return dict(store)

    @x.paint
    def x_html(data, ctx):
        return f"<i>{data['v']}</i>"

    r1 = ch.refresh("X:root", etags={"X:root": "1"})
    assert r1.ok and len(r1.ops) == 0
    store["v"] = 2
    r2 = ch.refresh("X:root", etags={"X:root": "1"})
    assert any(o.get("op") == "morph" for o in r2.ops)


def test_command_can_return_result():
    ch = Channel.boot(secret=SECRET)

    @ch.on("X.deny", refresh=["nope"])
    def deny(ctx):
        return ch.fail.forbidden("no")

    ChannelTest(ch).call("X.deny").assert_fail("forbidden")
