"""Repository paths for tests at any depth under tests/."""
from __future__ import annotations

from pathlib import Path

# tests/helpers/paths.py → parents[2] = repo root
REPO_ROOT = Path(__file__).resolve().parents[2]
SRC = REPO_ROOT / "src"
STATIC = SRC / "ux_channel" / "static"
DOCS = REPO_ROOT / "docs"
EXAMPLES = REPO_ROOT / "examples"
