"""Regressions from chaotic standalone apps (auth context + navigate soft-block)."""

from __future__ import annotations

import threading

from fastapi import FastAPI

from ux_channel import Channel, ChannelConfig, Principal, Region
from ux_channel.protocol.types import Result
from ux_channel.protocol.ops import navigate, push_url


def _ch(**kw):
    app = FastAPI()
    cfg = ChannelConfig.development(
        secret="dev-secret-key-32chars-minimum!!!!",
        **kw,
    )
    return Channel.boot(app, config=cfg), app


def test_auth_principal_with_default_timeout():
    """auth=True must see dispatch(principal=) even when handler runs in timeout thread."""
    ch, _ = _ch()
    assert ch.registry.action_timeout_s > 0  # development still has timeout

    @ch.on(name="Auth.me", auth=True)
    def me():
        return ch.done(notice="secret")

    cap = ch.registry.mint("Auth.me", {})
    denied = ch.registry.dispatch({"v": "1", "action": "Auth.me", "args": {}, "cap": cap})
    assert not denied.ok

    ok = ch.registry.dispatch(
        {"v": "1", "action": "Auth.me", "args": {}, "cap": cap},
        principal=Principal.of("user-1"),
    )
    assert ok.ok, ok.error


def test_navigate_unsafe_is_noop_not_internal():
    ch, _ = _ch()

    @ch.on(name="Nav.bad")
    def nav():
        return Result.success(navigate("javascript:alert(1)"))

    cap = ch.registry.mint("Nav.bad", {})
    r = ch.registry.dispatch({"v": "1", "action": "Nav.bad", "args": {}, "cap": cap})
    assert r.ok, r.error
    assert not any(o.get("op") == "navigate" for o in r.ops)
    assert any(o.get("op") == "noop" for o in r.ops)


def test_push_url_unsafe_noop():
    op = push_url("data:text/html,x")
    assert (op.get("op") if isinstance(op, dict) else op.to_dict().get("op")) == "noop"


def test_draft_edit_concurrency_400():
    ch, _ = _ch()
    ch.draft.set("counter", 0)

    def worker():
        for _ in range(50):
            with ch.draft.edit("counter", default=0) as slot:
                slot.value = int(slot.value or 0) + 1

    th = [threading.Thread(target=worker) for _ in range(8)]
    for t in th:
        t.start()
    for t in th:
        t.join()
    assert ch.draft.get("counter") == 400


def test_live_ws_publish_roundtrip():
    from fastapi.testclient import TestClient

    ch, app = _ch()

    class Board(Region):
        def render(self, ctx=None):
            return f"<span>{self.state_get('v', 0)}</span>"

    b = Board(ch, uid="board").mount()
    ch.live.bind("public.board", b)
    client = TestClient(app)
    with client.websocket_connect("/ux-channel/ws?topics=public.board") as ws:
        for _ in range(3):
            try:
                ws.receive_json()
            except Exception:
                break
        b.state_set("v", 99)
        ch.live.publish("public.board")
        got = None
        for _ in range(8):
            msg = ws.receive_json()
            if msg.get("type") == "result":
                got = msg
                break
        assert got is not None
        assert "99" in str(got)


def test_roles_with_principal():
    ch, _ = _ch()

    @ch.on(name="Admin.x", auth=True, roles=["admin"])
    def admin():
        return ch.done(notice="admin")

    cap = ch.registry.mint("Admin.x", {})
    denied = ch.registry.dispatch(
        {"v": "1", "action": "Admin.x", "args": {}, "cap": cap},
        principal=Principal.of("u", roles=["user"]),
    )
    assert not denied.ok
    allowed = ch.registry.dispatch(
        {"v": "1", "action": "Admin.x", "args": {}, "cap": cap},
        principal=Principal.of("a", roles=["admin"]),
    )
    assert allowed.ok, allowed.error
