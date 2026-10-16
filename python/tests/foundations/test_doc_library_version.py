"""Gate: every doc that states the library version states the real one."""
from __future__ import annotations

import re
from pathlib import Path

from ux_channel import __version__

PY_ROOT = Path(__file__).resolve().parents[2]
REPO_ROOT = PY_ROOT.parent
# "**Library version:** 0.1.1", "> Library version **0.1.1**", ...
LINE = re.compile(r"library version[\s:*]*v?(\d+\.\d+\.\d+)", re.IGNORECASE)
# Historical records keep the versions they were written for.
HISTORY = {"CHANGELOG.md", "SECURITY_AUDIT.md"}


def _docs():
    for path in REPO_ROOT.rglob("*.md"):
        parts = set(path.parts)
        if parts & {"node_modules", ".git", "archive", "target"}:
            continue
        if path.name in HISTORY:
            continue
        yield path


def test_library_version_lines_match_package():
    stale = []
    for path in _docs():
        for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            for m in LINE.finditer(line):
                if m.group(1) != __version__:
                    stale.append(f"{path.relative_to(REPO_ROOT)}:{n}: {m.group(1)}")
    assert not stale, f"library version != {__version__}:\n" + "\n".join(stale)


def test_gate_actually_finds_version_lines():
    hits = sum(
        1 for p in _docs() for _ in LINE.finditer(p.read_text(encoding="utf-8"))
    )
    assert hits >= 5


def test_diagram_script_reads_package_version():
    text = (PY_ROOT / "scripts" / "generate_diagrams.py").read_text()
    assert not re.search(r'LIB_VER\s*=\s*"\d', text)
