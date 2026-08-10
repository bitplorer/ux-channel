"""Brutal multipass stability for the production surface (no duals, concurrent, chaos)."""

from __future__ import annotations

import concurrent.futures
import json
import threading
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from ux_channel import Channel, ChannelConfig, Intent, Result
from ux_channel.demo import attr_string, demo_button, script_tags
from ux_channel.dx import DAY1_CHANNEL_API
from ux_channel.error_map import ERROR_HTTP_STATUS, http_status_for
from ux_channel.placement import Placement

SECRET = "brutal-prod-surface-secret-key-32chars!!"


def _boot(**kw: Any) -> tuple[FastAPI, Channel, TestClient]:
    app = FastAPI()
    base = dict(
        secret=SECRET,
        allow_memory_stores=True,
        require_cap=True,
        enforce_same_origin=False,
        require_channel_header=False,
    )
    base.update(kw)
    ch = Channel.boot(app, config=ChannelConfig.development(**base))
    return app, ch, TestClient(app)


def test_day1_closed_and_no_alias_map():
    assert len(DAY1_CHANNEL_API) == 13
    assert "refresh" not in DAY1_CHANNEL_API
    assert "diagnose" not in DAY1_CHANNEL_API
    assert not hasattr(Channel, "aliases")
    assert not hasattr(Result, "fail")
    app, ch, _ = _boot()
    for n in DAY1_CHANNEL_API:
        assert hasattr(ch, n), n
    assert not hasattr(ch, "multi")
    assert not hasattr(ch, "page")
    assert not hasattr(ch, "button")
    assert "ch" not in dir(ch.fail)  # no FailFlow.ch leak
    assert "update" not in dir(ch.draft)
    assert not hasattr(ch, "search")


def test_done_signature_no_dual_kwargs():
    import inspect

    _, ch, _ = _boot()
    sig = str(inspect.signature(ch.done))
    for bad in ("toast", "navigate", "keys", "**"):
        assert bad not in sig, sig
    rsig = str(inspect.signature(ch.refresh))
    assert "toast" not in rsig and "keys" not in rsig


def test_handler_success_fail_refresh_stack_http():
    app, ch, c = _boot(require_cap=False)

    @ch.region("ctr")
    def ctr(ctx):
        return f"<b data-channel-id='ctr'>{int(ch.draft.get('n', 0) or 0)}</b>"

    @ch.on(refresh=["ctr"])
    def inc():
        ch.draft.change("n", lambda n: int(n or 0) + 1, default=0)
        return ch.done(notice="ok", meta={"v": ch.draft.get("n")})

    @ch.on
    def bad():
        return ch.fail.valid({"x": ["req"]}, region="ctr", html="<b data-channel-id='ctr'>0</b>")

    @ch.on
    def pure():
        return ch.done(refresh=["ctr"])

    r = c.post("/ux-channel/action", json={"action": "inc", "args": {}})
    assert r.status_code == 200 and r.json()["ok"]
    body = r.json()
    assert any(o.get("op") == "toast" for o in body["ops"])
    assert any(o.get("op") == "morph" for o in body["ops"])
    assert body.get("meta", {}).get("v") == 1

    r2 = c.post("/ux-channel/action", json={"action": "bad", "args": {}})
    assert r2.status_code == 422
    assert r2.json()["error"]["code"] == "validation"

    r3 = c.post("/ux-channel/action", json={"action": "pure", "args": {}})
    assert r3.status_code == 200 and r3.json()["ok"]


def test_done_refresh_empty_overrides_stack():
    _, ch, _ = _boot(require_cap=False)

    @ch.region("z")
    def z(ctx):
        return "Z"

    @ch.on(refresh=["z"])
    def a():
        return ch.done(refresh=[])

    r = ch.registry.dispatch(Intent(action="a", args={}, cap=ch.sign("a", {})))
    assert r.ok
    assert r.ops == [] or not any(o.get("op") == "morph" for o in r.ops)


def test_concurrent_draft_change_no_lost_updates():
    _, ch, _ = _boot(require_cap=False)

    @ch.on
    def bump():
        ch.draft.change("n", lambda x: int(x or 0) + 1, default=0)
        return ch.done()

    def one(_i):
        return ch.registry.dispatch(
            Intent(action="bump", args={}, cap=ch.sign("bump", {}))
        ).ok

    with concurrent.futures.ThreadPoolExecutor(max_workers=32) as ex:
        oks = list(ex.map(one, range(250)))
    assert all(oks)
    assert ch.draft.get("n") == 250


def test_concurrent_http_actions_idempotent_and_mixed():
    app, ch, c = _boot(require_cap=False)

    @ch.on(idempotent=True)
    def ping(n: int = 0):
        return ch.done(meta={"n": n})

    @ch.on
    def boom():
        return ch.fail.code("conflict", "x")

    errs = []
    lock = threading.Lock()

    def one(i):
        if i % 17 == 0:
            r = c.post("/ux-channel/action", json={"action": "boom", "args": {}})
            if r.status_code != 409:
                with lock:
                    errs.append(("boom", r.status_code, r.text[:60]))
        else:
            r = c.post("/ux-channel/action", json={"action": "ping", "args": {"n": i}})
            if r.status_code != 200 or not r.json().get("ok"):
                with lock:
                    errs.append(("ping", r.status_code, r.text[:60]))

    with concurrent.futures.ThreadPoolExecutor(max_workers=40) as ex:
        list(ex.map(one, range(400)))
    assert errs == [], errs[:8]


def test_error_map_all_codes_roundtrip_and_http():
    for code, status in ERROR_HTTP_STATUS.items():
        r = Result.failure(code, "m")
        assert http_status_for(r) == status, code
        d = r.to_dict()
        assert d["ok"] is False and d["error"]["code"] == code


def test_control_sign_cap_dispatch():
    _, ch, _ = _boot()

    @ch.on
    def add(sku: str = "x"):
        return ch.done(meta={"sku": sku})

    attrs = ch.control(add, trust_sku="a1").as_dict()
    assert "data-channel-action" in attrs and "data-channel-cap" in attrs
    cap = attrs["data-channel-cap"]
    r = ch.registry.dispatch(
        Intent(action="add", args={"sku": "a1"}, cap=cap)
    )
    assert r.ok and r.meta.get("sku") == "a1"


def test_media_plugin_placement_and_demo_render():
    _, ch, _ = _boot()
    p = ch.media.plugin("lobby", sub="u1", mode="mesh")
    assert p.mode == "mesh"
    pl = p.to_placement()
    assert isinstance(pl, Placement)
    assert pl.kind == "media"
    html = script_tags(p)
    assert "ux-channel.js" in html or "ux-webrtc" in html
    s = attr_string(p)
    assert "data-uid" in s or s == "" or "media" in s or "webrtc" in s


def test_bridge_mount_spec_and_patch_map():
    _, ch, _ = _boot()
    spec = ch.bridge.mount_spec("chart-1", package="@uid/chart")
    assert isinstance(spec, Placement) or hasattr(spec, "attrs")
    r = ch.patch({"A": "<em>1</em>", "B": "<em>2</em>"}, notice="multi")
    assert r.ok
    ops = r.ops
    assert sum(1 for o in ops if o.get("op") == "morph") >= 2
    assert any(o.get("op") == "toast" for o in ops)


def test_fail_closed_set_speech():
    _, ch, _ = _boot()
    assert ch.fail.auth().error.code == "unauthorized"
    assert ch.fail.forbidden().error.code == "forbidden"
    assert ch.fail.rate().error.code == "rate_limited"
    assert ch.fail.code("not_found", "x").error.code == "not_found"
    public = {n for n in dir(ch.fail) if not n.startswith("_")}
    assert public <= {"auth", "forbidden", "rate", "valid", "code"}


def test_ice_servers_not_html():
    _, ch, _ = _boot()
    servers = ch.webrtc.ice.servers()
    assert isinstance(servers, list) and servers
    assert not hasattr(ch.webrtc.ice, "html")


def test_region_ssr_html_and_refresh_power():
    _, ch, _ = _boot()

    @ch.region("s")
    def s(ctx):
        return f"<span>{ch.draft.get('t', 'x')}</span>"

    assert "x" in ch.html("s", wrap=False)
    ch.draft.set("t", "y")
    r = ch.refresh("s")
    assert r.ok and any("y" in (o.get("html") or "") for o in r.ops)


def test_chaos_malformed_intents():
    _, ch, c = _boot(require_cap=False)
    # empty action
    r = c.post("/ux-channel/action", json={"action": "", "args": {}})
    assert r.status_code in (400, 422)
    # unknown action
    r = c.post("/ux-channel/action", json={"action": "nope.x", "args": {}})
    assert r.status_code in (404, 422, 400)
    # not json
    r = c.post("/ux-channel/action", data="not-json", headers={"content-type": "application/json"})
    assert r.status_code >= 400


def test_help_prefer_codec_not_alias_map():
    h = Channel.help("prefer")
    assert "done" in h and "media.plugin" in h
    assert "Result.failure" in h


def test_stress_mixed_workers_state_and_morph():
    app, ch, c = _boot(require_cap=False)

    @ch.region("bag")
    def bag(ctx):
        n = int(ch.draft.get("n", 0) or 0)
        return f"<i data-channel-id='bag'>{n}</i>"

    @ch.on(refresh=["bag"])
    def add():
        ch.draft.change("n", lambda n: int(n or 0) + 1, default=0)
        return ch.done()

    @ch.on
    def snap():
        return ch.done(refresh=["bag"])

    def worker(i):
        if i % 3 == 0:
            return c.post("/ux-channel/action", json={"action": "snap", "args": {}}).status_code
        return c.post("/ux-channel/action", json={"action": "add", "args": {}}).status_code

    with concurrent.futures.ThreadPoolExecutor(24) as ex:
        codes = list(ex.map(worker, range(180)))
    assert all(c == 200 for c in codes)
    # adds = 2/3 of 180 roughly
    n = int(ch.draft.get("n") or 0)
    assert n >= 100


def test_demo_button_still_works_with_control_path():
    _, ch, _ = _boot()

    @ch.on
    def hit():
        return ch.done()

    html = demo_button(ch, "Go", hit)
    assert "data-channel-action" in html and "Go" in html
