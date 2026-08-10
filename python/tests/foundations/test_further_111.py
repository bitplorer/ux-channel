"""v1.11 further improvements."""

from __future__ import annotations

from ux_channel import Channel, SafeHtml, mark_safe
from ux_channel.demo import attr_string, demo_button, demo_page, demo_scripts, script_tags
from ux_channel.asgi.pipeline import preflight_action
from ux_channel.asgi.core import status_for
from ux_channel.types import Result
from ux_channel.config import ChannelConfig


SECRET = "dev-secret-key-32chars-minimum!!!!"


def test_preflight_missing_header():
    cfg = ChannelConfig.development(SECRET, require_channel_header=True, rate_limit_per_minute=0)
    fail = preflight_action(
        {"content-type": "application/json", "content-length": "2"},
        config=cfg,
    )
    assert fail is not None
    result, status, _ = fail
    assert status == 403 and result.error.code == "forbidden"


def test_preflight_ok_with_header():
    cfg = ChannelConfig.development(SECRET, require_channel_header=True, rate_limit_per_minute=0)
    fail = preflight_action(
        {
            "content-type": "application/json",
            "content-length": "2",
            "x-channel": "1",
        },
        config=cfg,
    )
    assert fail is None


def test_safe_html_and_mark_safe():
    assert isinstance(mark_safe("<b>x</b>"), SafeHtml)
    ch = Channel.boot(secret=SECRET)
    r = ch.patch("X:root", mark_safe("<em>ok</em>"))
    assert r.ok and "<em>ok</em>" in r.ops[0]["html"]


def test_link_and_submit():
    from ux_channel.demo import demo_link, demo_submit

    ch = Channel.boot(secret=SECRET)
    ch.register("X.do", lambda: Result.success())
    a = demo_link(ch, "Go", "X.do", args={"a": 1}, target="X:root")
    assert "data-channel-action=" in a and "Go" in a and a.startswith("<a ")
    assert 'type="submit"' in demo_submit("Save")


def test_page_auto_dev_inspector():
    ch = Channel.boot(secret=SECRET)
    html = demo_page(ch, "<p>x</p>")
    assert "data-channel-dev" in html
    assert "ux-inspector.js" in html
    html2 = demo_page(ch, "<p>x</p>", dev=False, inspector=False)
    assert "data-channel-dev" not in html2


def test_status_upgrade_required():
    r = Result.failure("upgrade_required", "please upgrade")
    assert status_for(r) == 426
