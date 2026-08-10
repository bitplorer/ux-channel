"""Golden path: fail-closed prod, ChannelTest, state, CLI."""

from __future__ import annotations

import secrets
from pathlib import Path

import pytest

from ux_channel import (
    Channel,
    ChannelConfig,
    ChannelTest,
    MemoryStateStore,
    Result,
)
from ux_channel.ops_dx.cli import main as cli_main
from ux_channel.host.factory import create_channel


SECRET = "prod-secret-key-32chars-minimum!!!!!"


def test_production_fails_without_durable_or_opt_in():
    cfg = ChannelConfig.production(SECRET)
    assert cfg.allow_memory_stores is False
    with pytest.raises(ValueError, match="durable stores|allow_memory"):
        create_channel(config=cfg, app=None, host=None)


def test_production_ok_with_allow_memory():
    cfg = ChannelConfig.production(SECRET, allow_memory_stores=True)
    reg, _ = create_channel(config=cfg, app=None, host=None)
    assert reg is not None


def test_development_boot_state_and_diagnose():
    ch = Channel.boot(secret=SECRET)
    assert isinstance(ch.state, MemoryStateStore)
    ch.state.set("Cart:root", {"n": 1})
    assert ch.state.get("Cart:root")["n"] == 1
    d = ch.diagnose()
    assert d["state"] == "MemoryStateStore"
    assert d["environment"] == "development"


def test_channel_test_fluent():
    ch = Channel.boot(secret=SECRET)

    @ch.action("Counter.inc")
    def inc(n: int = 0):
        return ch.patch("Counter:root", f"<b>{n + 1}</b>", notice="ok")

    (
        ChannelTest(ch)
        .call("Counter.inc", n=2)
        .assert_ok()
        .assert_morph("Counter:root", contains="3")
        .assert_notice("ok")
    )


def test_fail_auth_helper():
    ch = Channel.boot(secret=SECRET)
    r = ch.fail.auth()
    assert not r.ok and r.error.code == "unauthorized"


def test_region_decorator():
    ch = Channel.boot(secret=SECRET)

    @ch.region("Box:root")
    def box(ctx):
        return {"color": ctx.key("color", "red")}

    @box.paint
    def box_html(data, ctx):
        return f'<div data-channel-id="Box:root" style="color:{data["color"]}">x</div>'

    @ch.on("Box.paint", refresh=["Box:root"])
    def paint(color: str = "red", ctx=None):
        return ch.done(refresh=["Box:root"], scope={"color": color})

    r = ChannelTest(ch).call("Box.paint", color="blue").assert_ok()
    assert "blue" in r.html_for("Box:root") or "blue" in str(r.ops)


def test_cli_check_and_new(tmp_path: Path, monkeypatch):
    assert cli_main(["info"]) == 0
    assert cli_main(["check", "--env", "development"]) == 0
    assert (
        cli_main(["check", "--env", "production", "--secret", SECRET, "--allow-memory"])
        == 0
    )
    assert cli_main(["check", "--env", "production", "--secret", SECRET]) == 1
    out = tmp_path / "app.py"
    assert cli_main(["new", "--path", str(out)]) == 0
    assert "Channel.boot" in out.read_text()


def test_observe_dev_maps_trace():
    cfg = ChannelConfig.development(SECRET, observe="off")
    assert cfg.trace_enabled is False
    cfg2 = ChannelConfig.development(SECRET, observe="dev")
    assert cfg2.trace_enabled is True
