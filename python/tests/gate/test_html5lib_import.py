"""html5lib checks HTML in both modes.

An HTML patch is refused when html5lib cannot be imported, the parser
raises, or a second parse of the cleaned output disagrees. Plain text and
non-HTML ops still pass when the import is missing.
"""

from __future__ import annotations

import importlib
import sys

import pytest

from ux_channel.render.morph_policy import apply_morph_policy, strip_dangerous_html
from ux_channel.security import security as security_mod

_HTML = '<b onclick="window.PWN(1)">ok</b>'


def _restore_morph_policy() -> None:
    import ux_channel.render.morph_policy as morph_policy

    importlib.reload(morph_policy)
    security_mod.apply_morph_policy = morph_policy.apply_morph_policy


def test_off_mode_patch_runs_when_html5lib_is_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """HTML is refused. Plain text and non-HTML ops still pass."""
    import ux_channel.render.morph_policy as morph_policy

    names = [
        name
        for name in list(sys.modules)
        if name == "html5lib" or name.startswith("html5lib.")
    ]
    for name in names:
        monkeypatch.setitem(sys.modules, name, None)
    monkeypatch.setitem(sys.modules, "html5lib", None)
    try:
        reloaded = importlib.reload(morph_policy)
        ops = reloaded.apply_morph_policy(
            [
                {"op": "swap", "target": "#t", "html": _HTML},
                {"op": "swap", "target": "#t", "html": "Saved."},
                {"op": "set_text", "target": "#t", "text": "hello"},
                {"op": "navigate", "href": "/ok"},
            ],
            policy="off",
        )
    finally:
        monkeypatch.undo()
        _restore_morph_policy()
    assert ops[0]["html"] == ""
    assert "onclick" not in ops[0]["html"].lower()
    assert ops[1]["html"] == "Saved."
    assert ops[2]["text"] == "hello"
    assert ops[3]["href"] == "/ok"


def test_off_mode_parse_failure_refuses_the_fragment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _boom(self, *args, **kwargs):
        raise RuntimeError("parse")

    monkeypatch.setattr("html5lib.HTMLParser.parseFragment", _boom)
    ops = apply_morph_policy(
        [{"op": "swap", "target": "#t", "html": _HTML}],
        policy="off",
    )
    assert ops[0]["html"] == ""


def test_off_mode_second_parse_disagreement_refuses_the_fragment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import html5lib

    real = html5lib.HTMLParser.parseFragment
    seen = {"n": 0}

    def _wrapped(self, html, *args, **kwargs):
        seen["n"] += 1
        fragment = real(self, html, *args, **kwargs)
        if seen["n"] >= 2:
            fragment.text = (fragment.text or "") + "DIFF"
        return fragment

    monkeypatch.setattr("html5lib.HTMLParser.parseFragment", _wrapped)
    ops = apply_morph_policy(
        [{"op": "swap", "target": "#t", "html": "<b>ok</b>"}],
        policy="off",
    )
    assert ops[0]["html"] == ""


def test_strict_patch_is_refused_when_html5lib_import_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    real_import = __import__

    def _blocked(name, globals=None, locals=None, fromlist=(), level=0):  # noqa: A002
        if name == "html5lib" or name.startswith("html5lib."):
            raise ImportError("html5lib blocked")
        return real_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr("builtins.__import__", _blocked)
    ops = apply_morph_policy(
        [{"op": "swap", "target": "#t", "html": _HTML}],
        policy="strict",
    )
    assert ops[0]["html"] == ""
    assert "onclick" not in ops[0]["html"].lower()


def test_strict_patch_is_refused_when_the_parser_raises(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _boom(self, *args, **kwargs):
        raise RuntimeError("parse")

    monkeypatch.setattr("html5lib.HTMLParser.parseFragment", _boom)
    ops = apply_morph_policy(
        [{"op": "swap", "target": "#t", "html": "<b>ok</b>"}],
        policy="strict",
    )
    assert ops[0]["html"] == ""
    assert strip_dangerous_html("<b>ok</b>") == ""
