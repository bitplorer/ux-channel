"""Low-friction organic API — auto uid/action, button(fn), page(*parts)."""

from ux_channel import Channel, Intent
from ux_channel.render.kit import attr_string, demo_button, demo_page, demo_scripts, script_tags

SECRET = "dev-secret-key-32chars-minimum!!!!"


def test_auto_uid_and_action_with_fn_button():
    ch = Channel.boot(secret=SECRET)

    @ch.region
    def cart_badge(ctx):
        return f"<b>{ch.draft.get('n', 0)}</b>"

    assert cart_badge.uid == "cart.badge"

    @ch.on(refresh=[cart_badge])
    def add(product_id: str = "sku"):
        ch.draft.set("n", ch.draft.get("n", 0) + 1)

    assert add.action == "add"
    html = demo_button(ch, "Add", add, trust={"product_id": "sku"})
    assert 'data-channel-action="add"' in html
    assert "cart.badge" in html  # auto target

    page = demo_page(ch, cart_badge, demo_button(ch, "Add", add, trust={"product_id": "sku"}))
    assert "cart.badge" in page and "data-channel-action" in page

    r = ch.registry.dispatch(
        Intent(action="add", args={"product_id": "sku"}, cap=ch.mint("add", {"product_id": "sku"}))
    )
    assert r.ok
    assert any("1" in o.get("html", "") for o in r.ops if o.get("op") == "morph")


def test_explicit_still_works():
    ch = Channel.boot(secret=SECRET)

    @ch.region("x.root")
    def x(ctx):
        return "X"

    @ch.on("X.bump", refresh=[x])
    def bump():
        return None

    r = ch.registry.dispatch(Intent(action="X.bump", args={}, cap=ch.mint("X.bump", {})))
    assert r.ok


def test_split_mode():
    ch = Channel.boot(secret=SECRET)

    @ch.region
    def item(ctx):
        return {"v": 2}

    @item.paint
    def item_html(data, ctx):
        return f"v={data['v']}"

    assert "v=2" in ch.html(item, wrap=False)


def test_ch_on_works():
    ch = Channel.boot(secret=SECRET)

    @ch.region
    def r(ctx):
        return "ok"

    @ch.on(refresh=[r])
    def touch():
        return None

    assert touch.action == "touch"
