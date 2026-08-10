"""Stunning ux-fx bridge presets — factory DX, ops, registration."""

from __future__ import annotations

from fastapi import FastAPI

from ux_channel import Channel, ChannelConfig
from ux_channel.bridges import (
    AuroraBridge,
    ConfettiBridge,
    CountUpBridge,
    FX_SCRIPT,
    LottieBridge,
    ParticlesBridge,
    SpotlightBridge,
)
from ux_channel.bridge_preset_gen import list_known_presets
from ux_channel.demo import fx_script_tags


def _ch():
    return Channel.boot(
        FastAPI(),
        config=ChannelConfig.development(
            secret="x" * 40, allow_memory_stores=True, require_cap=False
        ),
    )


def test_catalog_includes_fx():
    keys = {p["key"] for p in list_known_presets()}
    for k in ("confetti", "particles", "aurora", "countup", "spotlight", "lottie"):
        assert k in keys, k


def test_confetti_factory_burst_ops():
    ch = _ch()
    fx = ConfettiBridge(ch)
    win = fx("win", theme="gold", particle_count=80)
    r = win.burst()
    assert r.ok
    ops = r.ops
    assert any(o.get("op") == "bridge.call" and o.get("method") == "burst" for o in ops)
    spec = win.mount_spec()
    assert spec.attrs["data-channel-bridge-package"] == "ux-fx/confetti"
    assert "gold" in str(win.props()["colors"]) or win.props()["theme"] == "gold"


def test_particles_commit_and_pulse():
    ch = _ch()
    hero = ParticlesBridge(ch)("hero", count=40, theme="ember")
    r = hero.commit(count=70)
    assert r.ok
    assert any(o.get("op") == "bridge.update" for o in r.ops)
    r2 = hero.pulse()
    assert any(o.get("method") == "pulse" for o in r2.ops)


def test_aurora_themes():
    ch = _ch()
    bg = AuroraBridge(ch, "bg", theme="sunset")
    props = bg.props()
    assert props["theme"] == "sunset"
    assert len(props["colors"]) >= 3
    r = bg.pause()
    assert any(o.get("method") == "pause" for o in r.ops)


def test_countup_set_value():
    ch = _ch()
    mrr = CountUpBridge(ch)("mrr", value=1000, prefix="$", theme="cyan")
    r = mrr.set_value(2500)
    assert r.ok
    assert any(o.get("method") == "setValue" for o in r.ops)
    assert mrr.props()["value"] == 2500.0
    assert mrr.props()["prefix"] == "$"


def test_spotlight_and_lottie():
    ch = _ch()
    card = SpotlightBridge(ch)("card", theme="gold")
    assert "rgba" in card.props()["color"]
    r = card.commit(radius=300)
    assert r.ok
    lot = LottieBridge(ch)("ok", src="https://example.com/a.json", loop=False)
    assert lot.props()["src"].endswith("a.json")
    assert lot.props()["loop"] is False
    r2 = lot.play()
    assert any(o.get("method") == "play" for o in r2.ops)


def test_fx_script_helper():
    assert "ux-fx.js" in FX_SCRIPT
    tags = fx_script_tags()
    assert "ux-bridge.js" in tags and "ux-fx.js" in tags


def test_factory_requires_island():
    ch = _ch()
    fx = ConfettiBridge(ch)
    try:
        fx.burst()
        assert False, "expected TypeError"
    except TypeError:
        pass
