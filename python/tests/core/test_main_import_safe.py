"""ux_channel.__main__ must not run CLI when imported (pkgutil, tools)."""

import importlib
import subprocess
import sys


def test_import_main_module_is_noop():
    # re-import; must not SystemExit
    mod = importlib.import_module("ux_channel.__main__")
    assert hasattr(mod, "main")
    assert mod.__name__ == "ux_channel.__main__"


def test_python_m_ux_channel_still_works():
    r = subprocess.run(
        [sys.executable, "-m", "ux_channel", "info"],
        capture_output=True,
        text=True,
        timeout=30,
        env={**dict(**__import__("os").environ), "PYTHONPATH": "src"},
        cwd=".",
    )
    assert r.returncode == 0
    assert "ux-channel" in (r.stdout + r.stderr)
