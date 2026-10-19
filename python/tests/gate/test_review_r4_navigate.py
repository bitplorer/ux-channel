"""Review r4: strict navigate must follow the browser, not urlparse.

A backslash, tab, newline, or other control character is refused. An
http(s) scheme that is not followed by exactly ``//`` is refused. An empty
hostname never matches. With no request origin, only a single-slash
relative path is allowed unless the host is on ``allowed_hosts``.
"""

from __future__ import annotations

import json

from ux_channel.security.security import filter_outbound_ops

_TRICKS = (
    "https://evil.test\\@app.test/",
    "https:\\\\evil.test/",
    "https:/\\evil.test/",
    "https:///evil.test/",
    "http:evil.test/",
    "https://evil.test\\.app.test/",
)


def _nav(href: str, **kwargs: object) -> dict:
    ops = filter_outbound_ops(
        [{"op": "navigate", "href": href}],
        policy="strict",
        **kwargs,  # type: ignore[arg-type]
    )
    return ops[0]


def test_strict_navigate_refuses_browser_open_redirects() -> None:
    for href in _TRICKS:
        op = _nav(href, origin_host="app.test", allowed_hosts=("app.test",))
        assert op["op"] == "noop", href
        assert "evil.test" not in json.dumps(op)


def test_strict_navigate_refuses_controls_and_a_scheme_without_slashes() -> None:
    for href in ("https://app.test/\tok", "https://app.test/\nok", "http:evil.test/"):
        op = _nav(href, origin_host="app.test")
        assert op["op"] == "noop", repr(href)


def test_empty_hostname_never_matches_a_missing_origin() -> None:
    for href in ("https:\\\\evil.test/", "https:///evil.test/", "http:evil.test/"):
        op = _nav(href, origin_host=None, allowed_hosts=())
        assert op["op"] == "noop", href
        assert "evil.test" not in json.dumps(op)


def test_no_origin_allows_only_a_single_slash_path() -> None:
    assert _nav("/ok", origin_host=None)["href"] == "/ok"
    for href in ("//evil.test/", "/\\evil.test/", "https://evil.test/"):
        assert _nav(href, origin_host=None)["op"] == "noop", href
    listed = _nav(
        "https://cdn.test/a",
        origin_host=None,
        allowed_hosts=("cdn.test",),
    )
    assert listed["op"] == "navigate"
    assert listed["href"] == "https://cdn.test/a"


def test_strict_navigate_keeps_the_request_host() -> None:
    kept = _nav("https://app.test/ok", origin_host="app.test")
    assert kept["op"] == "navigate"
    assert kept["href"] == "https://app.test/ok"
