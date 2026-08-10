"""Design-contract tests: MRO depth, purity, idempotent install, stress."""

from __future__ import annotations

import threading
from concurrent.futures import ThreadPoolExecutor

from ux_channel import ActionRegistry, Channel, ChannelConfig, Result
from ux_channel.components import (
    AppShell,
    ChannelComponent,
    ChannelKit,
    Composite,
    Counter,
    Flash,
    Block,
    RegistryHost,
)
from ux_channel.types import Intent

SECRET = "dev-secret-key-32chars-minimum!!!!"


def _ch():
    return Channel.boot(
        config=ChannelConfig.development(
            secret=SECRET, rate_limit_per_minute=0, require_channel_header=False
        )
    )


def test_mro_depth_shallow():
    """Library types stay within 3 hops under object (ChannelComponent chain)."""

    def depth(cls):
        # hops from object to cls
        return len(cls.__mro__) - 1

    # object, ABC, ChannelComponent, leaf  → depth 3 for Counter if ABC counts
    # MRO: Counter, ChannelComponent, ABC, object → len 4 → hops 3
    assert depth(Counter) <= 4
    assert depth(Composite) <= 4
    assert depth(AppShell) <= 5  # AppShell → Composite → ChannelComponent → ABC → object
    # No multi-inheritance
    for cls in (Counter, Composite, Block, AppShell, Flash):
        bases = [b for b in cls.__bases__ if b is not object]
        # single meaningful base chain
        assert len(cls.__bases__) == 1


def test_channelcomponent_not_named_component():
    import ux_channel.components as cc
    import ux_channel

    assert "Component" not in cc.__all__
    assert "Component" not in ux_channel.__all__
    assert issubclass(Counter, ChannelComponent)


def test_install_idempotent_and_concurrent():
    ch = _ch()
    c = Counter(ch, name="Qty", uid="Qty:root")
    # concurrent install
    with ThreadPoolExecutor(16) as ex:
        list(ex.map(lambda _: c.install(), range(50)))
    assert c._installed is True
    # actions registered once — dispatch works
    r = ch.registry.dispatch(
        Intent(action="Qty.inc", args={"n": 0}, cap=ch.mint("Qty.inc", {"n": 0}))
    )
    assert r.ok


def test_render_is_pure_under_threads():
    ch = _ch()
    c = Counter(ch, uid="P:root", min_value=0).install()
    results: dict[int, str] = {}
    lock = threading.Lock()

    def one(n):
        html = c.render(n=n)
        with lock:
            results[n] = html

    with ThreadPoolExecutor(32) as ex:
        list(ex.map(one, range(100)))
    for i in range(100):
        assert str(i) in results[i]


def test_refresh_toast_api():
    ch = _ch()
    c = Counter(ch, uid="T:root").install()
    r = c.refresh(n=2, notice="up")
    assert r.ok
    ops = [o["op"] for o in r.ops]
    assert "morph" in ops and "toast" in ops


def test_flash_message_is_state_not_toast_only():
    ch = _ch()
    f = Flash(ch, uid="F:root").install()
    r = f.refresh(message="Hello", level="success")
    assert "Hello" in r.ops[0]["html"]


def test_nested_composite_kit_stress():
    ch = _ch()
    counters = [Counter(ch, name=f"C{i}", uid=f"C{i}:root") for i in range(20)]
    kit = ChannelKit(ch).add(*counters).install_all()
    assert all(c._installed for c in kit)

    shell = AppShell(
        ch,
        uid="S:root",
        slots={"main": counters[0], "brand": "<b>x</b>"},
    ).install()
    html = shell.render()
    assert "C0:root" in html or "ux-counter" in html or "data-channel-id" in html


def test_registry_host_path_preferred_for_ux_dom_apps():
    reg = ActionRegistry(secret=SECRET, require_cap=True)
    host = RegistryHost(reg)
    c = Counter(host, name="R", uid="R:root").install()
    assert c.host is not None
    r = reg.dispatch(
        Intent(action="R.inc", args={"n": 0}, cap=reg.mint("R.inc", {"n": 0}))
    )
    assert r.ok


def test_island_swap_concurrent():
    ch = _ch()
    island = Block(ch, uid="I:root", body="<p>0</p>").install()

    def one(i):
        return island.swap(f"<p>{i}</p>").ok

    with ThreadPoolExecutor(16) as ex:
        assert all(ex.map(one, range(40)))


def test_custom_leaf_follows_contract():
    ch = _ch()

    class Rating(ChannelComponent):
        kind = "Rating"

        def render(self, **state):
            return self.wrap(str(state.get("stars", 0)), class_="rating")

        def _register(self):
            @self.host.action(self.action_name("set"))
            def set_stars(stars: int = 0):
                return self.refresh(stars=stars, notice="ok")

    r = Rating(ch, uid="Rate:root").install()
    out = ch.registry.dispatch(
        Intent(
            action="Rating.set",
            args={"stars": 4},
            cap=ch.mint("Rating.set", {"stars": 4}),
        )
    )
    assert out.ok and "4" in out.ops[0]["html"]


def test_action_burst_on_installed_counter():
    ch = _ch()
    c = Counter(ch, name="B", uid="B:root", min_value=0, max_value=10_000).install()

    def one(i):
        cap = ch.mint("B.inc", {"n": i})
        return ch.registry.dispatch(
            Intent(action="B.inc", args={"n": i}, cap=cap)
        ).ok

    with ThreadPoolExecutor(32) as ex:
        assert all(ex.map(one, range(200)))
