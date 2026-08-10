"""Channel Components — bare-bones primitives + widgets + host adapters."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from ux_channel import ActionRegistry, Channel, ChannelConfig, Result
from ux_channel.demo import attr_string, demo_button, demo_page, demo_scripts, script_tags
from ux_channel.components import (
    Badge,
    ChannelComponent,
    ChannelKit,
    Confirm,
    Counter,
    Field,
    Flash,
    Form,
    ListView,
    Modal,
    RegistryHost,
    Step,
    Tabs,
    Wizard,
    region_button,
    region_morph,
    region_root,
    to_html,
    uid_sel,
)
from ux_channel.types import Intent

SECRET = "dev-secret-key-32chars-minimum!!!!"


def _ch(app=None):
    cfg = ChannelConfig.development(
        secret=SECRET, rate_limit_per_minute=0, require_channel_header=False
    )
    return Channel.boot(app, config=cfg)


def test_no_component_name_clash_export():
    import ux_channel
    import ux_channel.components as cc

    assert "Component" not in ux_channel.__all__
    assert "Component" not in cc.__all__
    assert hasattr(cc, "ChannelComponent")
    assert not hasattr(cc, "Component")


def test_primitives_region_root_and_sel():
    assert uid_sel("Cart:badge") == '[data-channel-id="Cart:badge"]'
    assert uid_sel("#x") == "#x"
    html = region_root("A:r", "<i>1</i>", class_="box", id="a")
    assert 'data-channel-id="A:r"' in html and 'class="box"' in html


def test_to_html_ux_dom_like_and_markup():
    class UxDomish:
        def __render__(self):
            return "<em>u</em>"

    class Markupish:
        def __html__(self):
            return "<b>m</b>"

    assert to_html(UxDomish()) == "<em>u</em>"
    assert to_html(Markupish()) == "<b>m</b>"
    assert to_html(None) == ""
    assert to_html("raw") == "raw"
    assert "<" in to_html("<script>")  # escaped fallback


def test_region_morph_result():
    r = region_morph("X:root", "<p>hi</p>", notice="ok")
    assert r.ok and len(r.ops) == 2
    assert r.ops[0]["op"] == "morph"


def test_registry_host_without_channel_facade():
    reg = ActionRegistry(secret=SECRET, require_cap=True)
    host = RegistryHost(reg)
    counter = Counter(host, name="Qty", uid="Qty:root", min_value=0).install()
    assert "Qty:root" in counter.render(n=0)
    r = reg.dispatch(
        Intent(action="Qty.inc", args={"n": 0}, cap=reg.sign("Qty.inc", {"n": 0}))
    )
    assert r.ok
    assert "1" in r.ops[0]["html"]


def test_region_button_bare_registry():
    reg = ActionRegistry(secret=SECRET, require_cap=True)
    btn = region_button(reg, "+", "X.inc", args={"n": 1}, target="X:root")
    assert "data-channel-cap=" in btn and "data-channel-action=" in btn


def test_counter_via_channel():
    ch = _ch()
    c = Counter(ch, uid="Shop:qty", min_value=0, max_value=5).install()
    r = ch.registry.dispatch(
        Intent(action="Counter.inc", args={"n": 1}, cap=ch.sign("Counter.inc", {"n": 1}))
    )
    assert r.ok


def test_counter_http():
    app = FastAPI()
    ch = _ch(app)
    counter = Counter(ch, name="Qty", uid="Qty:root").install()

    @app.get("/")
    def index():
        return demo_page(ch, counter.html(n=0))

    client = TestClient(app)
    assert "Qty:root" in client.get("/").text
    cap = ch.sign("Qty.inc", {"n": 0})
    r = client.post(
        "/ux-channel/action",
        json={"v": "1", "action": "Qty.inc", "args": {"n": 0}, "cap": cap},
    )
    assert r.status_code == 200 and r.json()["ok"]


def test_form_validation():
    ch = _ch()

    def validate(values):
        return {} if "@" in values.get("email", "") else {"email": ["bad"]}

    form = Form(
        ch,
        name="Login",
        uid="Login:root",
        fields=[Field("email", "Email", required=True)],
        validate=validate,
        success_redirect="/ok",
    ).install()
    bad = ch.registry.dispatch(
        Intent(
            action="Login.submit",
            form={"email": "x"},
            cap=ch.sign("Login.submit", {}),
        )
    )
    assert not bad.ok
    good = ch.registry.dispatch(
        Intent(
            action="Login.submit",
            form={"email": "a@b.co"},
            cap=ch.sign("Login.submit", {}),
        )
    )
    assert good.ok and any(o.get("op") == "navigate" for o in good.ops)


def test_modal_flash_badge_tabs():
    ch = _ch()
    m = Modal(ch, uid="Dlg:root", title="T").install()
    assert m.open(body="<p>x</p>").ok
    assert m.close().ok
    flash = Flash(ch, uid="App:flash").install()
    assert "Saved" in flash.show("Saved", level="success").ops[0]["html"]
    badge = Badge(ch, uid="Cart:badge", label="Cart").install()
    assert "3" in badge.set(3).ops[0]["html"]
    tabs = Tabs(ch, panels={"a": "A", "b": "B"}).install()
    r = ch.registry.dispatch(
        Intent(
            action="Tabs.select",
            args={"active": "b"},
            cap=ch.sign("Tabs.select", {"active": "b"}),
        )
    )
    assert r.ok and "B" in r.ops[0]["html"]


def test_list_view():
    ch = _ch()
    data = [f"item-{i}" for i in range(25)]

    def loader(q, page, per_page):
        f = [x for x in data if q in x] if q else data
        s = (page - 1) * per_page
        return f[s : s + per_page], len(f)

    lv = ListView(ch, name="Cat", uid="Cat:list", loader=loader, per_page=10).install()
    r = ch.registry.dispatch(
        Intent(
            action="Cat.page",
            args={"q": "", "page": 2},
            cap=ch.sign("Cat.page", {"q": "", "page": 2}),
        )
    )
    assert r.ok and "item-10" in r.ops[0]["html"]


def test_wizard():
    ch = _ch()

    w = Wizard(
        ch,
        name="On",
        steps=[Step("One", ["f"]), Step("Two", ["f"])],
        render_step=lambda step, data, errors: f'<input id="f" name="f" value="{data.get("f","")}"/>',
        validate_step=lambda step, data: {"f": ["need"]} if step == 0 and not data.get("f") else {},
        on_finish=lambda data: ch.redirect("/done"),
    ).install()
    assert not ch.registry.dispatch(
        Intent(action="On.next", args={"step": 0}, cap=ch.sign("On.next", {"step": 0}))
    ).ok
    assert ch.registry.dispatch(
        Intent(
            action="On.next",
            args={"step": 0, "f": "x"},
            cap=ch.sign("On.next", {"step": 0, "f": "x"}),
        )
    ).ok


def test_confirm():
    ch = _ch()
    done = {"n": 0}

    def do_delete():
        done["n"] = 1
        return Result.success()

    Confirm(
        ch, name="Del", uid="Del:btn", on_confirm=do_delete, once=False, use_modal=False
    ).install()
    assert ch.registry.dispatch(
        Intent(action="Del.ask", args={}, cap=ch.sign("Del.ask", {}))
    ).ok
    assert ch.registry.dispatch(
        Intent(action="Del.run", args={}, cap=ch.sign("Del.run", {}))
    ).ok
    assert done["n"] == 1


def test_channel_kit():
    ch = _ch()
    kit = ChannelKit(ch).add(Counter(ch, name="A"), Flash(ch, name="B", uid="B:f")).install_all()
    assert all(c._installed for c in kit.items)


def test_custom_channel_component():
    ch = _ch()

    class Rating(ChannelComponent):
        kind = "Rating"

        def render(self, **state):
            return self.wrap("★" * int(state.get("stars", 0)), class_="rating")

        def _register(self):
            @self.host.action(self.action_name("set"))
            def set_stars(stars: int = 0):
                return self.refresh(stars=stars)

    r = Rating(ch, uid="Rate:root").install()
    out = ch.registry.dispatch(
        Intent(action="Rating.set", args={"stars": 3}, cap=ch.sign("Rating.set", {"stars": 3}))
    )
    assert out.ok and "★★★" in out.ops[0]["html"]


def test_morph_accepts_ux_dom_like_fragment():
    ch = _ch()

    class Frag:
        def __render__(self):
            return region_root("Z:root", "<i>z</i>")

    class Box(ChannelComponent):
        kind = "Box"

        def render(self, **state):
            return region_root(self.uid, "")

        def _register(self):
            pass

    box = Box(ch, uid="Z:root").install()
    res = box.morph(Frag())
    assert res.ok and "z" in res.ops[0]["html"]
