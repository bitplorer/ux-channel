"""Runtime Placement + body_attrs (no HTML on Channel)."""

from fastapi import FastAPI

from ux_channel import Channel, ChannelConfig
from ux_channel.paint.demo import attr_string, demo_page, demo_scripts, script_tags


def _ch():
    return Channel.boot(
        FastAPI(),
        config=ChannelConfig.development(
            secret="dev-secret-key-32chars-minimum!!!!",
            allow_memory_stores=True,
            require_cap=False,
        ),
    )


def test_runtime_placement_has_scripts():
    ch = _ch()
    p = ch.runtime()
    assert p.kind == "runtime"
    urls = [s.src for s in p.scripts]
    assert any("ux-channel.js" in u for u in urls)
    assert any("ux-bridge.js" in u for u in urls)


def test_demo_scripts_from_runtime():
    ch = _ch()
    html = demo_scripts(ch)
    assert "ux-channel.js" in html
    assert "<script" in html


def test_body_attrs_dict_not_html():
    ch = _ch()
    attrs = ch.body_attrs(push_topic="t1")
    assert isinstance(attrs, dict)
    assert attrs["data-channel-endpoint"].endswith("/action")
    assert attrs["data-channel-push-topic"] == "t1"
    s = attr_string(attrs)
    assert "data-channel-push-topic" in s


def test_demo_page():
    ch = _ch()
    doc = demo_page(ch, "<h1>Hi</h1>", title="T")
    assert "<!doctype html>" in doc.lower() or "<!DOCTYPE" in doc
    assert "Hi" in doc
    assert "ux-channel.js" in doc


def test_no_html_facade_on_channel():
    ch = _ch()
    # document HTML façade removed; region SSR ``html`` is product API
    for name in ("page", "scripts", "button", "link", "form", "body_attr_string"):
        assert not hasattr(ch, name), name
    assert hasattr(ch, "html")  # RegionBook SSR
    assert hasattr(ch, "runtime") and hasattr(ch, "body_attrs")
