"""A missing html5lib logs once per process, then stays quiet.

The message is ``HTML patches refused until installed``. A later refusal
does not log again. Reloading the module starts a new process lifetime
for the flag.
"""

from __future__ import annotations

import importlib
import logging
import sys

import pytest

from ux_channel.security import security as security_mod

_LOGGER = "ux_channel.render.morph_policy.html5lib"
_MESSAGE = "HTML patches refused until installed"


def _restore() -> None:
    import ux_channel.render.morph_policy as morph_policy

    importlib.reload(morph_policy)
    security_mod.apply_morph_policy = morph_policy.apply_morph_policy


def test_missing_html5lib_logs_once_then_stays_quiet(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    import ux_channel.render.morph_policy as morph_policy

    for name in list(sys.modules):
        if name == "html5lib" or name.startswith("html5lib."):
            monkeypatch.setitem(sys.modules, name, None)
    monkeypatch.setitem(sys.modules, "html5lib", None)
    try:
        reloaded = importlib.reload(morph_policy)
        with caplog.at_level(logging.ERROR, logger=_LOGGER):
            assert reloaded.strip_off_html("<b>one</b>") == ""
            assert reloaded.strip_dangerous_html("<b>two</b>") == ""
        messages = [
            record.getMessage()
            for record in caplog.records
            if record.name == _LOGGER and record.levelno >= logging.ERROR
        ]
    finally:
        monkeypatch.undo()
        _restore()
    assert messages == [_MESSAGE]
