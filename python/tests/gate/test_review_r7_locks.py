"""Locks for behaviour r7 must not regress.

Open redirects, off-mode scrub, the 256 nesting boundary, strict
comments, and a bogus stream policy. These already held; the assertions
are what the mutants die on.
"""

from __future__ import annotations

import logging

import pytest

from ux_channel.host.config import ChannelConfig
from ux_channel.render.morph_policy import strip_dangerous_html, strip_off_html
from ux_channel.security.security import filter_outbound_ops
from ux_channel.transport.push import stream_filter_args

_KEEP = "KEEP-LOCK"


def _nav(href: str, **kwargs: object) -> dict:
    ops = filter_outbound_ops(
        [{"op": "navigate", "href": href}],
        policy="strict",
        **kwargs,  # type: ignore[arg-type]
    )
    return ops[0]


def test_open_redirect_suffix_and_empty_userinfo_are_refused() -> None:
    """Q12 evilapp.test, Q14 app.test.evil.test, Q20 https://@evil.test/."""
    for href in (
        "https://evilapp.test/",
        "https://app.test.evil.test/",
        "https://@evil.test/",
    ):
        op = _nav(href, origin_host="app.test", allowed_hosts=("app.test",))
        assert op["op"] == "noop", href
    empty = _nav("https://@evil.test/", origin_host="evil.test")
    assert empty["op"] == "noop"


def test_strict_navigate_keeps_userinfo_port_case_and_subdomain() -> None:
    kept = {
        "https://evil.test@app.test/": "app.test",
        "https://user:pass@app.test/ok": "app.test",
        "https://app.test:8443/ok": "app.test",
        "https://APP.TEST/ok": "app.test",
        "https://cdn.app.test/a": "app.test",
    }
    for href, origin in kept.items():
        op = _nav(href, origin_host=origin, allowed_hosts=("app.test",))
        assert op["op"] == "navigate", href
        assert "evil.test/" not in op["href"] or href.startswith("https://evil.test@")
    port_origin = _nav("https://app.test/ok", origin_host="app.test:8443")
    assert port_origin["op"] == "navigate"
    assert port_origin["href"] == "https://app.test/ok"


def test_off_mode_scrubs_nested_animation_srcset_and_handler_animation() -> None:
    for depth in (1, 3, 8):
        html = (
            "<div>" * depth
            + '<svg><animate attributeName="href" values="javascript:alert(1)"></animate></svg>'
            + "</div>" * depth
            + f"<b>{_KEEP}</b>"
        )
        out = strip_off_html(html)
        assert "<animate" not in out.lower(), depth
        assert "javascript:" not in out.lower(), depth
        assert _KEEP in out
    srcset = strip_off_html(f'<img srcset="javascript:alert(1) 1x"><b>{_KEEP}</b>')
    assert "javascript:" not in srcset.lower()
    assert _KEEP in srcset
    handler = strip_off_html(
        f'<svg><set attributeName=" onload " to="alert(1)"></set><b>{_KEEP}</b></svg>'
    )
    assert "<set" not in handler.lower()
    assert _KEEP in handler


def test_nesting_boundary_keeps_256_and_refuses_257(
    caplog: pytest.LogCaptureFixture,
) -> None:
    for depth in (255, 256):
        html = "<div>" * depth + _KEEP + "</div>" * depth
        out = strip_off_html(html)
        assert _KEEP in out, depth
        assert out != ""
    html = "<div>" * 257 + _KEEP + "</div>" * 257
    with caplog.at_level(logging.ERROR):
        refused = strip_off_html(html)
    assert refused == ""
    assert any("nesting refused" in record.getMessage() for record in caplog.records)


def test_strict_mode_drops_comments() -> None:
    out = strip_dangerous_html(f"<!-- secret --><b>{_KEEP}</b>")
    assert "secret" not in out
    assert _KEEP in out
    assert "<!--" not in out


def test_stream_filter_args_refuses_bogus() -> None:
    class _Cfg:
        morph_html_policy = "bogus"
        navigate_allowed_hosts = ()

    class _Reg:
        push_bus = None
        config = _Cfg()

    with pytest.raises(ValueError):
        stream_filter_args(_Reg(), _Cfg())


def test_development_config_accepts_the_lock_hosts() -> None:
    cfg = ChannelConfig.development(
        secret="lock-secret-32chars-minimum!!!",
        morph_html_policy="strict",
        navigate_allowed_hosts=("app.test",),
        observe="off",
        allow_memory_stores=True,
    )
    assert cfg.navigate_allowed_hosts == ("app.test",)
