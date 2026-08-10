"""DX façade (Channel / UiBuilder) tests."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from ux_channel import Result, Channel, sel
from ux_channel.demo import attr_string, demo_button, demo_page, demo_scripts, script_tags
from ux_channel.types import Intent

SECRET = "dev-secret-key-32chars-minimum!!!!"


def test_sel_helpers():
    assert sel("Counter:root") == '[data-channel-id="Counter:root"]'
    assert sel("#x") == "#x"


def test_channel_boot_and_action_cycle():
    app = FastAPI()
    ch = Channel.boot(app, secret=SECRET)

    def view(n: int) -> str:
        return ch.wrap(
            "Counter:root",
            f"<strong>{n}</strong>"
            + demo_button(ch, "+", "Counter.inc", trust={"n": n}, target="Counter:root"),
        )

    @ch.action("Counter.inc")
    def inc(n: int = 0):
        return ch.patch("Counter:root", view(n + 1), notice=f"n={n+1}")

    c = TestClient(app)
    cap = ch.sign("Counter.inc", {"n": 0})
    r = c.post(
        "/ux-channel/action",
        json={"v": "1", "action": "Counter.inc", "args": {"n": 0}, "cap": cap},
        headers={"X-Channel": "1"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    assert any(o.get("op") == "morph" for o in body["ops"])
    assert any(o.get("op") == "toast" for o in body["ops"])


def test_ui_fail_validation():
    ch = Channel.boot(secret=SECRET, app=None)
    r = ch.fail.valid(
        {"email": ["required"]},
        region="Login:root",
        html="<form/>",
        focus="#email",
    )
    assert not r.ok
    assert r.error.code == "validation"
    ops = [o["op"] for o in r.ops]
    assert "morph" in ops and "focus" in ops  # toast/notice opt-in only


def test_multi_region():
    ch = Channel.boot(secret=SECRET)
    r = ch.patch({"A:root": "<a/>", "B:root": "<b/>"}, notice="done")
    assert r.ok and len(r.ops) == 3


def test_page_shell():
    ch = Channel.boot(secret=SECRET)
    html = demo_page(ch, "<p>x</p>", title="Demo", dev=True, inspector=True)
    assert "data-channel-endpoint" in html
    assert "ux-inspector.js" in html


def test_button_signs_cap():
    ch = Channel.boot(secret=SECRET)
    ch.register("X.y", lambda: Result.success())
    btn = demo_button(ch, "Go", "X.y", trust={"a": 1})
    assert "data-channel-cap=" in btn and "Go" in btn
