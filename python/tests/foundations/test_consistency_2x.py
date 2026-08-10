"""Anti-staleness: stable 0.1 surface."""

from __future__ import annotations

import importlib
import pkgutil

import pytest

import ux_channel
from ux_channel import Channel, Intent
from ux_channel.components.form import Field, Form

SECRET = "dev-secret-key-32chars-minimum!!!!"

REMOVED = (
    "view", "ok", "err", "sync", "notify", "search", "islands", "patterns", "bind", "do", "attrs", "shell", "document", "head",
    "island", "command", "login_required", "revalidate", "form_ok", "invalid",
    "draft_get",
)

REQUIRED = (
    "region", "on", "done", "fail", "html", "refresh", "patch", "notice",
    "filter", "draft", "control", "runtime", "body_attrs", "sign", "regions",
)


def test_all_submodules_import():
    fails = []
    for m in pkgutil.walk_packages(ux_channel.__path__, ux_channel.__name__ + "."):
        if m.name.endswith(".__main__"):
            continue
        try:
            importlib.import_module(m.name)
        except Exception as e:
            fails.append((m.name, str(e)))
    assert fails == []


def test_all_exports_exist():
    bad = [n for n in ux_channel.__all__ if not hasattr(ux_channel, n)]
    assert bad == []


def test_surface():
    ch = Channel.boot(secret=SECRET)
    for n in REMOVED:
        assert not hasattr(ch, n), n
    for n in REQUIRED:
        assert hasattr(ch, n), n


def test_form_validation():
    ch = Channel.boot(secret=SECRET)
    Form(ch, uid="F:root", fields=[Field("email", "Email", required=True)]).install()
    cap = ch.mint("Form.submit", {})
    r = ch.registry.dispatch(Intent(action="Form.submit", args={}, cap=cap))
    assert not r.ok
    assert r.error is not None
    assert r.error.code == "validation"


def test_region_refresh_on():
    ch = Channel.boot(secret=SECRET)

    @ch.region("app.flash")
    def flash(ctx):
        return {"message": "hi"}

    @flash.paint
    def flash_html(data, ctx):
        return f"<em>{data['message']}</em>"

    assert "hi" in ch.html("app.flash", wrap=False)
    assert ch.done(refresh=["app.flash"]).ok

    hits = []

    @ch.on("X.do", refresh=["app.flash"])
    def do():
        hits.append(1)
        return None

    r = ch.registry.dispatch(Intent(action="X.do", args={}, cap=ch.mint("X.do", {})))
    assert r.ok and hits == [1]


def test_unknown_region_message():
    ch = Channel.boot(secret=SECRET)
    with pytest.raises(KeyError, match="@ch.region"):
        ch.html("Nope:root")


def test_subject_on_context():
    ch = Channel.boot(secret=SECRET)
    ctx = ch.regions.context(scope={"user_id": "u1"})
    assert ctx.subject == "u1"
    assert ctx.actor == "u1"
    assert ctx.scope["user_id"] == "u1"
