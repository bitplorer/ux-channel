"""Review r4: policy spelling, fail-closed serialize, and one drop list.

None is off. An explicit blank, whitespace, or any other string raises at
config time and from the env var. A channel bus inherits that policy. A
PushBus with no channel is strict. A serializer error or a very deep
fragment is an empty patch and a log line, not a 500.
"""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path

import pytest

from ux_channel.host.config import ChannelConfig
from ux_channel.render.morph_policy import (
    _DROP_CONTENT,
    _DROP_TAG,
    apply_morph_policy,
    strip_dangerous_html,
)
from ux_channel.transport.push import PushBus
from ux_channel.transport.stream import resolve_stream_policy

_SECRET = "review-r4-secret-32chars-minimum!"
_STATIC = (
    Path(__file__).resolve().parents[2] / "src" / "ux_channel" / "static" / "ux-channel.js"
)
_NOSCRIPT = '<noscript><p title="</noscript><img src=x onerror=window.PWN(19)>">'
_TEMPLATE = "<template><img src=x onerror=window.PWN(53)></template><b>keep</b>"
_STYLE = "<svg><style>.x{color:red}</style><rect></rect></svg>"
_MATH = "<math><style>.x{color:red}</style><mi>a</mi></math>"


def _dev(**kwargs: object) -> ChannelConfig:
    return ChannelConfig.development(
        secret=_SECRET,
        observe="off",
        allow_memory_stores=True,
        **kwargs,  # type: ignore[arg-type]
    )


def test_unset_policy_is_off_and_blank_or_unknown_raises() -> None:
    assert _dev().morph_html_policy == "off"
    explicit = ChannelConfig(
        secret=_SECRET,
        environment="development",
        allow_memory_stores=True,
        morph_html_policy=None,  # type: ignore[arg-type]
    ).validate()
    assert explicit.morph_html_policy == "off"
    for bad in ("", " ", "\t", "\n", "strict ", "nope", "OFF"):
        with pytest.raises(ValueError):
            _dev(morph_html_policy=bad)


def test_env_policy_unset_is_off_and_blank_raises(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("UX_CHANNEL_SECRET", _SECRET)
    monkeypatch.setenv("UX_CHANNEL_ENV", "development")
    monkeypatch.setenv("UX_CHANNEL_ALLOW_MEMORY_STORES", "1")
    monkeypatch.delenv("UX_CHANNEL_MORPH_HTML_POLICY", raising=False)
    assert ChannelConfig.from_env().morph_html_policy == "off"
    for bad in ("", " ", "\t", "nope"):
        monkeypatch.setenv("UX_CHANNEL_MORPH_HTML_POLICY", bad)
        with pytest.raises(ValueError):
            ChannelConfig.from_env()
    monkeypatch.setenv("UX_CHANNEL_MORPH_HTML_POLICY", "strict")
    assert ChannelConfig.from_env().morph_html_policy == "strict"


def test_channel_bus_inherits_policy_and_a_bare_bus_is_strict() -> None:
    assert PushBus().outbound_policy() == "strict"
    assert resolve_stream_policy(None) == "strict"
    off = _dev(morph_html_policy="off")
    strict = _dev(morph_html_policy="strict")
    assert off.morph_html_policy == "off"
    assert strict.morph_html_policy == "strict"
    bus = PushBus()
    bus.morph_html_policy = "off"
    bus._policy_bound = True
    assert bus.outbound_policy() == "off"
    bare = PushBus()
    for bad in ("", " ", "nope"):
        bare.morph_html_policy = bad
        with pytest.raises(ValueError):
            bare.outbound_policy()


def test_serializer_error_refuses_the_patch_and_logs(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    def _boom(*_args: object, **_kwargs: object) -> str:
        raise RuntimeError("serialize")

    monkeypatch.setattr(
        "ux_channel.render.morph_policy._render",
        _boom,
    )
    with caplog.at_level(logging.ERROR):
        out = strip_dangerous_html("<b>ok</b>")
        ops = apply_morph_policy(
            [{"op": "swap", "target": "#t", "html": "<b>ok</b>"}],
            policy="strict",
        )
    assert out == ""
    assert ops[0]["html"] == ""
    assert caplog.records


def test_deep_nesting_refuses_the_patch_and_logs(
    caplog: pytest.LogCaptureFixture,
) -> None:
    html = "<div>" * 400 + "x" + "</div>" * 400
    with caplog.at_level(logging.ERROR):
        out = strip_dangerous_html(html)
    assert out == ""
    assert caplog.records
    assert "onerror" not in out.lower()


def test_scripting_on_keeps_a_stripped_noscript_breakout() -> None:
    out = strip_dangerous_html(_NOSCRIPT)
    assert "onerror" not in out.lower()
    assert "<img" in out.lower()


def test_template_element_is_dropped() -> None:
    out = strip_dangerous_html(_TEMPLATE)
    assert "<template" not in out.lower()
    assert "onerror" not in out.lower()
    assert "keep" in out


def test_svg_and_math_style_elements_are_dropped() -> None:
    svg = strip_dangerous_html(_STYLE)
    math = strip_dangerous_html(_MATH)
    assert "<style" not in svg.lower()
    assert "<rect" in svg.lower()
    assert "<style" not in math.lower()
    assert "<mi" in math.lower()


def _js_names(source: str, marker: str) -> set[str]:
    match = re.search(rf"var {marker} = (\[[\s\S]*?\]);", source)
    assert match, marker
    return set(json.loads(match.group(1)))


def test_client_and_server_share_one_drop_name_list() -> None:
    source = _STATIC.read_text(encoding="utf-8")
    assert _js_names(source, "DROP_CONTENT") == set(_DROP_CONTENT)
    assert _js_names(source, "DROP_VOID") == set(_DROP_TAG)
    minified = _STATIC.with_name("ux-channel.min.js").read_text(encoding="utf-8")
    assert _js_names(minified, "DROP_CONTENT") == set(_DROP_CONTENT)
    assert _js_names(minified, "DROP_VOID") == set(_DROP_TAG)
