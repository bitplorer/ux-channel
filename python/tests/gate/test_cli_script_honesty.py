"""Poetry console script uxchannel must import-resolve to the live CLI owner."""

from __future__ import annotations

import importlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
PYPROJECT = ROOT / "python" / "pyproject.toml"


def _poetry_scripts(text: str) -> dict[str, str]:
    """Tiny extractor — avoids adding a toml dependency to the gate."""
    scripts: dict[str, str] = {}
    in_scripts = False
    for raw in text.splitlines():
        line = raw.strip()
        if line.startswith("[") and line.endswith("]"):
            in_scripts = line == "[tool.poetry.scripts]"
            continue
        if not in_scripts or "=" not in line or line.startswith("#"):
            continue
        name, _, rest = line.partition("=")
        scripts[name.strip()] = rest.strip().strip('"').strip("'")
    return scripts


def test_uxchannel_console_script_import_resolves():
    text = PYPROJECT.read_text(encoding="utf-8")
    target = _poetry_scripts(text).get("uxchannel")
    assert target, "poetry script uxchannel missing"
    module_name, sep, attr = target.partition(":")
    assert sep and module_name and attr, target
    mod = importlib.import_module(module_name)
    fn = getattr(mod, attr)
    assert callable(fn)
    from ux_channel.devtools.cli import main as live_main

    assert fn is live_main
