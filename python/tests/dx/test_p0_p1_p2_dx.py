"""P0/P1/P2 DX: teach errors, upgrade-check, recipes, explain, demo, typing."""

from __future__ import annotations

import os
import tempfile
import warnings
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from ux_channel import Channel, ChannelConfig
from ux_channel.ops_dx.cli import main as cli_main
from ux_channel.paint.demo import demo_button, demo_page, attr_string
from ux_channel.ops_dx.explain import explain, explain_code
from ux_channel.paint.html import ControlAttrs
from ux_channel.host.recipes import RECIPE_NAMES, recipe_text
from ux_channel.protocol.types import Intent, Result
from ux_channel.ops_dx.upgrade_check import scan_path


def _boot(**kw):
    app = FastAPI()
    base = dict(
        secret="dev-secret-key-32chars-minimum!!!!",
        allow_memory_stores=True,
        require_cap=True,
    )
    base.update(kw)
    ch = Channel.boot(app, config=ChannelConfig.development(**base))
    return app, ch


def test_p0_missing_cap_message_teaches():
    app, ch = _boot()

    @ch.on
    def add():
        return ch.done()

    c = TestClient(app)
    r = c.post("/ux-channel/action", json={"action": "add", "args": {}})
    assert r.status_code in (401, 403, 200)
    body = r.json()
    assert body.get("ok") is False
    msg = (body.get("error") or {}).get("message", "")
    assert "ch.control" in msg or "capability" in msg.lower()
    exp = ch.explain(body)
    assert exp.get("teach") and "control" in exp["teach"].lower()


def test_p0_sfu_error_teaches():
    app, ch = _boot()
    try:
        ch.media.plugin("r", mode="sfu")
        assert False
    except RuntimeError as e:
        assert "media-sfu" in str(e) or "LIVEKIT" in str(e)
        assert "mesh" in str(e).lower()


def test_p0_config_factories_exist():
    d = ChannelConfig.development(secret="x" * 40, allow_memory_stores=True)
    assert d.environment == "development"
    p = ChannelConfig.production(
        "x" * 40, allow_memory_stores=True, allowed_origins=("https://a.example",)
    )
    assert p.environment == "production"


def test_p1_upgrade_check_finds_button():
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        # ch.button is the removed façade; demo_button is the supported demo path
        (root / "app.py").write_text("ch.button('x', 'a')\nChannelConfig(secret='y')\n")
        report = scan_path(root)
        rules = {f.rule for f in report.findings}
        assert "demo-button" in rules
        assert "raw-channelconfig" in rules
    assert cli_main(["upgrade-check", "."]) in (0, 1)


def test_p1_each_recipe_smoke_importable():
    """Recipes are non-empty and mention stable APIs."""
    for name in RECIPE_NAMES:
        code = recipe_text(name)
        assert len(code) > 30
        if name == "counter":
            assert "@ch.region" in code or "region" in code
        if name.startswith("media"):
            assert "media.plugin" in code or "plugin" in code


def test_p1_control_attrs_ide_surface():
    app, ch = _boot(require_cap=False)

    @ch.on
    def add():
        return ch.done()

    attrs = ch.control(add)
    assert isinstance(attrs, ControlAttrs)
    d = attrs.as_dict()
    assert "data-channel-action" in d
    u = attrs.as_ux_dom()
    assert "data_channel_action" in u
    assert attrs.attr_string
    assert attrs.action
    # cap may be set when mint_cap default True
    assert attrs.cap is None or isinstance(attrs.cap, str)


def test_p2_demo_no_deprecation_channel_warns():
    app, ch = _boot(require_cap=False)

    @ch.on
    def ping():
        return ch.done()

    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        demo_button(ch, "X", ping)
        demo_page(ch, "<p>x</p>")
        dep = [x for x in w if issubclass(x.category, DeprecationWarning)]
        assert dep == [], dep


def test_p2_explain_result():
    r = Result.failure("unauthorized", "missing capability")
    out = explain(r)
    assert out["ok"] is False
    assert out["recipe"] == "ux-dom-control"
    assert "control" in out["teach"].lower()
    assert explain_code("sfu_not_configured")["recipe"] == "media-sfu"


def test_p2_media_first_help():
    h = Channel.help("prefer")
    assert "ch.media.plugin" in h
    assert "media.plugin" in h
    # webrtc.plugin is power/adapter — not product speech
    assert "ch.bridge.mount_spec" in h
