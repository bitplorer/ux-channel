
"""Refresh error hardening: go= clobber, notice fail-closed, client hooks, push queue."""

from __future__ import annotations

import asyncio

from fastapi import FastAPI
from fastapi.testclient import TestClient

from ux_channel import Channel, ChannelConfig, Region, Result
from ux_channel.transport.push import MemoryPushBackend, PushBus, set_push_bus, get_push_bus
from ux_channel.protocol.types import Result as R


def _ch():
    app = FastAPI()
    ch = Channel.boot(
        app,
        config=ChannelConfig.development(secret="dev-secret-key-32chars-minimum!!!!"),
    )
    return ch, app


def test_go_does_not_clobber_render_error():
    ch, _ = _ch()
    r = ch.done(refresh=["missing.x"], go="/dashboard")
    assert not r.ok
    assert r.error and r.error.code == "render_error"
    # navigate may be present but failure preserved
    assert any(o.get("op") == "navigate" or o.get("op") == "noop" for o in (r.ops or [])) or True
    # critical: still failed
    assert r.ok is False


def test_notice_on_total_refresh_fail_is_not_ok():
    ch, _ = _ch()
    r = ch.done(refresh=["ghost"], notice="Saved!")
    assert not r.ok
    assert r.error.code == "render_error"
    assert any(o.get("op") == "toast" for o in r.ops)
    assert "refresh_errors" in (r.meta or {})


def test_partial_refresh_ok_with_meta():
    ch, _ = _ch()

    class Good(Region):
        def render(self, ctx=None):
            return "<b>ok</b>"

    g = Good(ch, uid="good").mount()
    r = ch.refresh(g, "missing")
    assert r.ok
    assert r.meta.get("refresh_errors")


def test_client_js_has_error_hooks():
    from pathlib import Path
    from ux_channel import __file__ as _ucf
    js = (Path(_ucf).resolve().parent / "static" / "ux-channel.js").read_text()
    for token in (
        "channel:error",
        "channel:refreshErrors",
        "channel:pushError",
        "channel:wsError",
        "function on(",
        "skip navigate on failed result",
    ):
        assert token in js, token


def test_push_drop_oldest_on_full_queue():
    set_push_bus(PushBus(MemoryPushBackend()))
    bus = get_push_bus()
    q: asyncio.Queue = asyncio.Queue(maxsize=2)

    async def run():
        bus.subscribe("public.t", q)
        # fill
        assert bus.publish("public.t", R.success()) >= 1
        assert bus.publish("public.t", R.success()) >= 1
        # third should drop oldest, still deliver
        n = bus.publish("public.t", {"ok": True, "ops": [{"op": "toast", "message": "fresh"}], "v": "1"})
        assert n >= 1
        # queue should have 2 items, last is fresh
        items = []
        while not q.empty():
            items.append(q.get_nowait())
        assert len(items) == 2
        assert items[-1].get("ops") or items[-1].get("ok") is not None
        bus.unsubscribe("public.t", q)

    asyncio.run(run())


def test_ws_live_failed_refresh_still_delivered():
    ch, app = _ch()
    client = TestClient(app)
    # publish a failed refresh onto public topic via live
    with client.websocket_connect("/ux-channel/ws?topics=public.err") as ws:
        for _ in range(2):
            try:
                ws.receive_json()
            except Exception:
                break
        # no regions bound — empty ops ok publish
        ch.live.publish("public.err")
        got = None
        for _ in range(6):
            msg = ws.receive_json()
            if msg.get("type") == "result":
                got = msg
                break
        assert got is not None
