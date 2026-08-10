"""ux_channel.__main__ must not run CLI when imported (pkgutil, tools)."""

from __future__ import annotations

import importlib
import os
import subprocess
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]  # python/
_SRC = _ROOT / "src"


def test_import_main_module_is_noop():
    # re-import; must not SystemExit
    mod = importlib.import_module("ux_channel.__main__")
    assert hasattr(mod, "main")
    assert mod.__name__ == "ux_channel.__main__"


def test_python_m_ux_channel_still_works():
    env = {**os.environ, "PYTHONPATH": str(_SRC)}
    r = subprocess.run(
        [sys.executable, "-m", "ux_channel", "info"],
        capture_output=True,
        text=True,
        timeout=30,
        env=env,
        cwd=str(_ROOT),
    )
    assert r.returncode == 0, r.stderr
    assert "ux-channel" in (r.stdout + r.stderr)
