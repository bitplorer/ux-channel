"""Class-style Region components — mount, action targeting, controls."""

from ux_channel import Channel, Intent, Region
from ux_channel.render.kit import attr_string, demo_button, demo_page, demo_scripts, script_tags

SECRET = "dev-secret-key-32chars-minimum!!!!"


def test_use_mount_render_action_button_page():
    ch = Channel.boot(secret=SECRET)

    class CartBadge(Region):
        def render(self, ctx):
            return f"<b>{self.ch.draft.get('n', 0)}</b>"

        @Region.action
        def add(self, product_id: str = "sku"):
            self.ch.draft.set("n", self.ch.draft.get("n", 0) + 1)

        @Region.action(refresh=False, name="cart.noop")
        def noop(self):
            return None

    badge = ch.use(CartBadge)
    assert badge.uid == "cart.badge"
    assert badge.add.action == "cart.badge.add"
    assert badge.add.refresh_uids == ["cart.badge"]
    assert "cart.badge" in badge.html()
    assert "cart.badge.add" in badge.button("Add", "add")
    assert "cart.noop" in badge.button("No", "noop")

    page = demo_page(ch, badge, badge.controls(("Add", "add", {"trust": {"product_id": "x"}})))
    assert "cart.badge" in page and "cart.badge.add" in page

    r = ch.registry.dispatch(
        Intent(
            action="cart.badge.add",
            args={"product_id": "x"},
            cap=ch.mint("cart.badge.add", {"product_id": "x"}),
        )
    )
    assert r.ok
    assert any(o.get("op") == "morph" and "1" in o.get("html", "") for o in r.ops)


def test_refresh_targets_class_and_self():
    ch = Channel.boot(secret=SECRET)

    class Header(Region):
        def render(self, ctx):
            return f"<h1>{self.ch.draft.get('n', 0)}</h1>"

    class Body(Region):
        def render(self, ctx):
            return f"<p>{self.ch.draft.get('n', 0)}</p>"

        @Region.action(refresh=[Header, True])
        def inc(self):
            self.ch.draft.set("n", self.ch.draft.get("n", 0) + 1)

    header = ch.use(Header)
    body = ch.use(Body)
    assert set(body.inc.refresh_uids) == {"header", "body"}

    r = ch.registry.dispatch(Intent(action="body.inc", args={}, cap=ch.mint("body.inc", {})))
    assert r.ok
    morphs = [o for o in r.ops if o.get("op") == "morph"]
    assert len(morphs) == 2
    assert any("header" in o["target"] for o in morphs)
    assert any("body" in o["target"] for o in morphs)


def test_explicit_uid_and_idempotent_mount():
    ch = Channel.boot(secret=SECRET)

    class Flash(Region):
        uid = "app.flash"

        def render(self, ctx):
            return "<div>flash</div>"

    a = Flash(ch).mount()
    b = a.mount()
    assert a is b
    assert a.uid == "app.flash"
    assert "app.flash" in a.html()


def test_function_and_class_style_coexist():
    ch = Channel.boot(secret=SECRET)

    @ch.region
    def note(ctx):
        return "note"

    class Box(Region):
        def render(self, ctx):
            return "box"

        @Region.action(refresh=[note, True])
        def poke(self):
            return None

    box = ch.use(Box)
    assert "note" in box.poke.refresh_uids and "box" in box.poke.refresh_uids
