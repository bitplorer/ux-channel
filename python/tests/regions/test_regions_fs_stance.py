"""Governing stance: core intact; file regions + AX shell opt-in."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from fastapi import FastAPI

from ux_channel import Channel, ChannelConfig, Intent, agents
from ux_channel.ops_dx.inspect_api import inspect_channel, inspect_enabled
from ux_channel.host.region_component import Region
from ux_channel.host.region_directory import path_to_uid, attach_region_directory


SECRET = "stance-regions-secret-key-32bytes!!!"


def _boot(**kw):
    app = FastAPI()
    return Channel.boot(
        app,
        config=ChannelConfig.development(
            secret=SECRET, allow_memory_stores=True, require_cap=False, **kw
        ),
    )


def test_path_to_uid():
    assert path_to_uid("pay/desk.py") == "pay.desk"
    assert path_to_uid("notice.py") == "notice"


def test_classic_region_still_works():
    ch = _boot()

    class Badge(Region):
        def render(self, ctx):
            return f"<b data-channel-id='{self.uid}'>{self.state_get('n', 0)}</b>"

        @Region.action
        def add(self):
            self.state_set("n", int(self.state_get("n", 0) or 0) + 1)

    b = Badge(ch).mount()
    assert "badge" in b.uid or b.uid
    wire = f"{b.uid}.add"
    assert wire in ch.registry.names()
    r = ch.registry.dispatch(Intent(action=wire, args={}, cap=ch.mint(wire, {})))
    assert r.ok


def test_ax_false_omitted_from_tools():
    ch = _boot()

    class Box(Region):
        uid = "box"

        def render(self, ctx):
            return "<div data-channel-id='box'></div>"

        @Region.action(summary="Visible")
        def go(self):
            pass

        @Region.action(ax=False, summary="Hidden")
        def help(self):
            pass

    Box(ch).mount()
    ag = agents(ch)
    names = [t["name"] for t in ag.tools_for()]
    assert "box.go" in names
    assert "box.help" not in names


def test_roles_filter_tools_for():
    ch = _boot()

    class Desk(Region):
        uid = "pay.desk"

        def render(self, ctx):
            return "<div data-channel-id='pay.desk'></div>"

        @Region.action(roles=("cashier",), summary="Pay")
        def pay_order(self):
            pass

        @Region.action(roles=("refund",), summary="Refund")
        def refund_order(self):
            pass

    Desk(ch).mount()
    ag = agents(ch)
    cash = [t["name"] for t in ag.tools_for(region="pay.desk", role="cashier")]
    assert "pay.desk.pay_order" in cash
    assert "pay.desk.refund_order" not in cash


def test_make_keyed_uid():
    ch = _boot()

    class Line(Region):
        uid = "cart.line"

        def render(self, ctx):
            return f"<div data-channel-id='{self.uid}'></div>"

        @Region.action
        def set_qty(self, qty: int = 1):
            self.state_set("qty", qty)

    inst = Line.make(ch, "42")
    assert inst.uid == "cart.line:42"
    assert "cart.line.42.set_qty" in ch.registry.names()


def test_inspect_dev_and_schema():
    ch = _boot(inspect_enabled=True)

    class Desk(Region):
        uid = "pay.desk"
        singleton = True

        def render(self, ctx):
            return '<div data-channel-id="pay.desk">ok</div>'

        @Region.action(roles=("cashier",))
        def pay_order(self):
            pass

    Desk(ch).mount()
    assert inspect_enabled(ch)
    snap = inspect_channel(ch, "pay.desk", role="cashier")
    assert snap["inspect_schema"] == 1
    assert snap["ok"] is True
    assert "ax" in snap and "pay.desk.pay_order" in snap["ax"]["allowed"]


def test_inspect_prod_disabled():
    app = FastAPI()
    ch = Channel.boot(
        app,
        config=ChannelConfig(
            secret=SECRET,
            environment="production",
            allow_memory_stores=True,
            require_cap=False,
            inspect_enabled=None,
            audit=False,
        ),
    )
    assert inspect_enabled(ch) is False
    snap = inspect_channel(ch, "x")
    assert snap.get("ok") is False


def test_discover_package(tmp_path, monkeypatch):
    # build temp package
    pkg = tmp_path / "tmp_regions_pkg"
    (pkg / "regions").mkdir(parents=True)
    (pkg / "regions" / "__init__.py").write_text("")
    (pkg / "regions" / "notice.py").write_text(
        "from ux_channel.host.region_component import Region\n"
        "class Notice(Region):\n"
        "    singleton = True\n"
        "    def render(self, ctx):\n"
        "        return '<div data-channel-id=\"%s\"></div>' % self.uid\n"
        "    @Region.action\n"
        "    def dismiss(self):\n"
        "        self.state_set('d', True)\n"
    )
    (pkg / "__init__.py").write_text("")
    sys.path.insert(0, str(tmp_path))
    try:
        ch = _boot(regions="tmp_regions_pkg.regions")
        d = attach_region_directory(ch)
        d.load("tmp_regions_pkg.regions")
        assert "notice" in d.uids()
        inst = d.mount("notice")
        assert inst._mounted
        assert any(n.endswith("dismiss") for n in ch.registry.names())
    finally:
        sys.path.remove(str(tmp_path))


def test_free_on_still_works():
    ch = _boot()

    @ch.on
    def free_act():
        return ch.done(notice="ok") if hasattr(ch, "done") else None

    # name free_act
    assert "free_act" in ch.registry.names() or any("free" in n for n in ch.registry.names())


def test_cli_region_add(tmp_path):
    from ux_channel.host.region_cli import cmd_region
    from types import SimpleNamespace
    from ux_channel.ops_dx.dx_log import get_log

    out = tmp_path / "regions"
    args = SimpleNamespace(
        region_action="add",
        path="pay/desk",
        recipe="payment",
        out=str(out),
        uid=None,
        force=False,
        strict=False,
    )
    assert cmd_region(args, get_log=get_log) == 0
    assert (out / "pay" / "desk.py").exists()
    text = (out / "pay" / "desk.py").read_text()
    assert "pay_order" in text
    assert 'uid = "pay.desk"' in text
