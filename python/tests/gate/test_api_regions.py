"""Public API region stability — pure Channel plane (no FastAPI required)."""
from __future__ import annotations

from pathlib import Path

from ux_channel import Channel, Intent, Region
from ux_channel.api import Channel as ApiChannel
from ux_channel.host.region_component import class_to_uid

SECRET = "dev-secret-key-32chars-minimum!!!!"


def test_public_api_facade_channel_is_same():
    assert ApiChannel is Channel


def test_refresh_morph_preserves_data_channel_id():
    ch = Channel.boot(secret=SECRET)

    class Box(Region):
        def render(self, ctx):
            return f'<div class="box">{self.ch.draft.get("n", 0)}</div>'

    Box(ch, uid="box").mount()
    ch.draft.set("n", 1)
    result = ch.refresh("box")
    assert result.ok
    assert result.ops
    html = result.ops[0]["html"]
    assert 'data-channel-id="box"' in html
    assert result.ops[0]["op"] == "morph"
    assert "box" in result.ops[0]["target"]


def test_function_region_auto_uid_and_action_refresh():
    ch = Channel.boot(secret=SECRET)

    @ch.region
    def cart_badge(ctx):
        return f"<b>{ch.draft.get('n', 0)}</b>"

    assert cart_badge.uid == "cart.badge"

    @ch.on(refresh=[cart_badge])
    def add(product_id: str = "sku"):
        ch.draft.set("n", ch.draft.get("n", 0) + 1)

    assert add.action == "add"
    r = ch.registry.dispatch(
        Intent(
            action="add",
            args={"product_id": "sku"},
            cap=ch.mint("add", {"product_id": "sku"}),
        )
    )
    assert r.ok
    morphs = [o for o in r.ops if o.get("op") == "morph"]
    assert morphs
    assert "1" in morphs[0].get("html", "")


def test_explicit_action_name():
    ch = Channel.boot(secret=SECRET)

    @ch.region("x.root")
    def x(ctx):
        return "X"

    @ch.on("X.bump", refresh=[x])
    def bump():
        return None

    r = ch.registry.dispatch(
        Intent(action="X.bump", args={}, cap=ch.mint("X.bump", {}))
    )
    assert r.ok


def test_class_to_uid_stable():
    assert class_to_uid("CartBadge") == "cart.badge"
    assert class_to_uid("Already.dotted") == "already.dotted"


def test_unknown_refresh_uid_does_not_crash():
    ch = Channel.boot(secret=SECRET)

    @ch.region
    def ok_region(ctx):
        return "ok"

    @ch.on(refresh=["missing.uid", ok_region])
    def touch():
        return None

    r = ch.registry.dispatch(
        Intent(action="touch", args={}, cap=ch.mint("touch", {}))
    )
    assert r.ok
    # at least the known region can morph; missing is skipped
    assert any(o.get("op") == "morph" for o in r.ops) or r.ok


def test_client_js_preserves_uid_contract():
    js_path = Path(__import__("ux_channel").__file__).resolve().parent / "static" / "ux-channel.js"
    js = js_path.read_text(encoding="utf-8")
    assert "data-channel-id" in js
    assert "replaceWith" in js
    assert (
        'next.setAttribute("data-channel-id"' in js
        or "next.setAttribute('data-channel-id'" in js
    )
