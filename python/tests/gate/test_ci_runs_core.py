"""CI must run python/tests/core, not only the gate suite.

Before this guard, verify.sh ran pytest on tests/gate only, so tests/core
(drift, compile and wire tests) could go red on main without CI noticing.
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def _pytest_lines() -> list[str]:
    text = (ROOT / "verify.sh").read_text(encoding="utf-8")
    return [ln for ln in text.splitlines() if "-m pytest" in ln]


def test_verify_sh_runs_gate_and_core() -> None:
    lines = _pytest_lines()
    assert any("python/tests/gate" in ln for ln in lines), lines
    assert any("python/tests/core" in ln for ln in lines), lines


def test_verify_sh_dep_probe_covers_core_test_deps() -> None:
    text = (ROOT / "verify.sh").read_text(encoding="utf-8")
    probe = re.search(r'python3 -c "import ([^"]+)"', text)
    assert probe, "verify.sh lost its dependency probe"
    mods = {m.strip() for m in probe.group(1).split(",")}
    assert {"hypothesis", "pytest_asyncio"} <= mods, mods


def test_core_test_deps_declared() -> None:
    req = (ROOT / "requirements-dev.txt").read_text(encoding="utf-8")
    for dep in ("hypothesis", "pytest-asyncio"):
        assert re.search(rf"^{dep}>=", req, re.M), dep
