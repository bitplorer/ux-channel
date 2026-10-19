"""html5lib is imported only by the strict sanitizer, and only lazily.

Off mode must still deliver a patch when ``html5lib`` cannot be imported.
Strict mode refuses the patch when that import fails or the parser raises.
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


def test_off_mode_patch_runs_when_html5lib_is_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    """Block the import. An off patch must still go through."""
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
            [{"op": "swap", "target": "#t", "html": _HTML}],
            policy="off",
        )
    finally:
        monkeypatch.undo()
        _restore_morph_policy()
    assert ops[0]["html"] == _HTML
    assert "onclick" in ops[0]["html"]


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
