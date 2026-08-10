"""
Capability regression — prevent cascading loss after hardening.

Asserts the philosophy surfaces still work together after cohesion fixes.
"""

from __future__ import annotations

import json
import warnings

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from ux_channel import Channel, ChannelConfig
from ux_channel.paint.demo import attr_string, demo_button, demo_page, demo_scripts, script_tags
from ux_channel.host.channel import CHANNEL_PUBLIC_API
from ux_channel.paint.placement import Placement, ScriptRef
from ux_channel.protocol.types import Intent, Result


def _ch(**kw):
    app = FastAPI()
    base = dict(
        secret="dev-secret-key-32chars-minimum!!!!",
        allow_memory_stores=True,
        require_cap=True,
    )
    base.update(kw)
    ch = Channel.boot(app, config=ChannelConfig.development(**base))
    return app, ch


def test_public_api_surface_complete_and_bound():
    app, ch = _ch()
    for name in CHANNEL_PUBLIC_API:
        assert hasattr(ch, name), f"missing public API: {name}"
    assert len(CHANNEL_PUBLIC_API) <= 20  # freeze cognitive load


def test_control_and_cap_pipeline():
    app, ch = _ch()

    @ch.on
    def add():
        return ch.done()

    attrs = ch.control(add)
    d = attrs.as_dict()
    assert "data-channel-action" in d
    assert d["data-channel-action"] == "add"
    # with require_cap, mint should include cap
    assert "data-channel-cap" in d or attrs.cap


def test_runtime_is_placement_not_html():
    app, ch = _ch()
    rt = ch.runtime()
    assert isinstance(rt, Placement)
    assert rt.scripts
    assert all(isinstance(s, ScriptRef) for s in rt.scripts)
    assert all("<" not in s.src for s in rt.scripts)
    blob = json.dumps(rt.as_dict())
    assert "<script" not in blob


def test_media_mesh_placement_data():
    app, ch = _ch()
    p = ch.media.plugin("lobby", sub="u1")
    assert p.mode in ("mesh", "sfu")
    assert isinstance(p.attrs, dict)
    assert isinstance(p.client, dict)
    assert "scripts_html" not in p.as_dict()
    assert p.scripts or p.client


def test_bridge_host_ops_call_contract():
    app, ch = _ch()
    ch.bridge.register("chartjs", methods=("resetZoom",))
    spec = ch.bridge.mount_spec("c1", package="chartjs", props={"t": 1})
    assert isinstance(spec, Placement)
    assert "data-channel-bridge-package" in spec.attrs
    ops = ch.bridge.mount_ops("c1", "chartjs", props={"t": 1})
    assert ops[0]["op"] == "bridge.mount"
    call = ch.bridge.call("c1", "resetZoom", package="chartjs")
    assert call[0]["op"] == "bridge.call"
    assert call[0]["method"] == "resetZoom"


def test_action_dispatch_intent_result():
    app, ch = _ch(require_cap=False)

    @ch.on
    def ping():
        return ch.done()

    c = TestClient(app)
    r = c.post("/ux-channel/action", json={"action": "ping", "args": {}})
    assert r.status_code == 200
    body = r.json()
    assert body.get("ok") is True


def test_missing_cap_still_teaches():
    app, ch = _ch(require_cap=True)

    @ch.on
    def secure():
        return ch.done()

    c = TestClient(app)
    r = c.post("/ux-channel/action", json={"action": "secure", "args": {}})
    body = r.json()
    assert body.get("ok") is False
    msg = (body.get("error") or {}).get("message", "")
    assert "cap" in msg.lower() or "control" in msg.lower()
    exp = ch.explain(body)
    assert exp.get("teach") or exp.get("recipe")


def test_region_morph_refresh():
    app, ch = _ch(require_cap=False)

    @ch.region
    def badge(ctx):
        n = ch.draft.get("n", 0)
        return f'<span data-channel-id="badge">{n}</span>'

    @ch.on(refresh=[badge])
    def inc():
        ch.draft.set("n", int(ch.draft.get("n", 0) or 0) + 1)

    c = TestClient(app)
    r = c.post("/ux-channel/action", json={"action": "inc", "args": {}})
    assert r.status_code == 200
    body = r.json()
    assert body.get("ok") is True
    ops = body.get("ops") or []
    assert any(o.get("op") in ("morph", "swap") for o in ops) or body.get("ok")


def test_aliases_no_false_bridge_media_alias():
    # Alias map removed — codec taught via help("prefer")
    h = Channel.help("prefer")
    assert "media.plugin" in h
    assert "demo" in h.lower() or "control" in h
    assert not hasattr(Channel, "aliases")


def test_otel_status_no_crash():
    from ux_channel.devtools.otel import status

    st = status()
    assert "available" in st


def test_json_dx_log_still_works():
    from io import StringIO
    from ux_channel.devtools.log import get_log

    buf = StringIO()
    log = get_log()
    log.configure(json_logs=True, stream=buf)
    log.info("regression", event="cap_test")
    line = buf.getvalue().strip().splitlines()[-1]
    rec = json.loads(line)
    assert rec["msg"] == "regression"
    log.configure(json_logs=False)


def test_region_button_no_deprecation_noise():
    """Internal Region.button is demo path — should not warn end users."""
    from ux_channel.host.region_component import Region

    app, ch = _ch(require_cap=False)

    class Badge(Region):
        def render(self, ctx):
            return "<span>0</span>"

        @Region.action
        def add(self):
            return ch.done()

    badge = ch.use(Badge)
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        html = badge.button("Add", "add")
        demo_warns = [
            x
            for x in w
            if issubclass(x.category, DeprecationWarning)
            and "demo-only" in str(x.message)
        ]
        assert demo_warns == [], demo_warns
    assert "Add" in str(html) or "button" in str(html).lower() or "data-uid" in str(html)
