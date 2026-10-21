"""First-party builtin bridge presets — factory DX, ops, registration."""

from __future__ import annotations

import json
import re
import tempfile
from importlib.resources import files

import pytest
from fastapi import FastAPI

from ux_channel import Channel, ChannelConfig
from ux_channel.bridges import (
    AuroraBridge,
    BUILTINS_SCRIPT,
    ConfettiBridge,
    CountUpBridge,
    LottieBridge,
    ParticlesBridge,
    SpotlightBridge,
)
from ux_channel.bridge.bridge_preset_gen import (
    create_bridge_preset,
    list_known_presets,
    resolve_preset_spec,
)
from ux_channel.devtools.errors import DxUsageError
from ux_channel.render.kit import builtins_script_tags


def _ch():
    return Channel.boot(
        FastAPI(),
        config=ChannelConfig.development(
            secret="x" * 40, allow_memory_stores=True, require_cap=False
        ),
    )


def test_catalog_includes_builtins():
    keys = {p["key"] for p in list_known_presets()}
    for k in ("confetti", "particles", "aurora", "countup", "spotlight", "lottie"):
        assert k in keys, k


_BUILTIN_PRESETS = ("confetti", "particles", "aurora", "countup", "spotlight")


def _js_builtin_keys() -> set[str]:
    js = (files("ux_channel") / "static" / "adapters" / "builtins.js").read_text()
    return {f"builtin/{n}" for n in re.findall(r'builtin\("([a-z]+)"', js)}


def test_confetti_preset_uses_key_registered_by_builtins_js():
    with tempfile.TemporaryDirectory() as td:
        root = create_bridge_preset(td, "confetti", force=True)
        assert 'PACKAGE = "builtin/confetti"' in (root / "preset.py").read_text()
    assert "builtin/confetti" in _js_builtin_keys()


@pytest.mark.parametrize("key", _BUILTIN_PRESETS)
def test_builtin_preset_writes_no_npm_dependency(key):
    with tempfile.TemporaryDirectory() as td:
        root = create_bridge_preset(td, key, force=True)
        assert resolve_preset_spec(key)["package"] in _js_builtin_keys()
        pkg = json.loads((root / "package.json").read_text())
        assert pkg["peerDependencies"] == {}
        assert "npm i" not in (root / "README.md").read_text()


def test_no_generated_package_json_mentions_ux_fx():
    with tempfile.TemporaryDirectory() as td:
        for row in list_known_presets():
            root = create_bridge_preset(td, row["key"], force=True)
            assert "ux-fx" not in (root / "package.json").read_text(), row["key"]


def test_unknown_preset_without_npm_fails_closed():
    with pytest.raises(DxUsageError) as exc:
        resolve_preset_spec("not-a-known-preset")
    assert exc.value.code == "bridge.npm_unknown"


def test_builtin_preset_refuses_npm_dependency():
    with pytest.raises(DxUsageError) as exc:
        resolve_preset_spec("confetti", npm="ux-fx")
    assert exc.value.code == "bridge.builtin_npm"


def test_confetti_factory_burst_ops():
    ch = _ch()
    fx = ConfettiBridge(ch)
    win = fx("win", theme="gold", particle_count=80)
    r = win.burst()
    assert r.ok
    ops = r.ops
    assert any(o.get("op") == "bridge.call" and o.get("method") == "burst" for o in ops)
    spec = win.mount_spec()
    assert spec.attrs["data-channel-bridge-package"] == "builtin/confetti"
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


def test_builtins_script_helper():
    assert "builtins.js" in BUILTINS_SCRIPT
    tags = builtins_script_tags()
    assert "ux-bridge.js" in tags and "builtins.js" in tags


def test_factory_requires_island():
    ch = _ch()
    fx = ConfettiBridge(ch)
    try:
        fx.burst()
        assert False, "expected TypeError"
    except TypeError:
        pass
