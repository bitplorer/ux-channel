"""Lock Python floor >=3.14 across pyproject + mypy + CI + leftover docs."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
PYPROJECT = ROOT / "python" / "pyproject.toml"
CI = ROOT / ".github" / "workflows" / "ci.yml"

FLOOR_DOCS = (
    ROOT / "README.md",
    ROOT / "CONTRIBUTING.md",
    ROOT / "python" / "CONTRIBUTING.md",
    ROOT / "python" / "docs" / "start" / "HOW_TO.md",
    ROOT / "docs" / "guides" / "first-app.md",
)


def test_poetry_python_floor_is_314_open():
    text = PYPROJECT.read_text(encoding="utf-8")
    assert 'python = ">=3.14,<4"' in text
    assert 'python = ">=3.10' not in text
    assert "Programming Language :: Python :: 3.14" in text
    assert "Programming Language :: Python :: 3.10" not in text


def test_mypy_and_ruff_lockstep_314():
    text = PYPROJECT.read_text(encoding="utf-8")
    assert 'python_version = "3.14"' in text
    assert 'python_version = "3.10"' not in text
    assert 'target-version = "py314"' in text


def test_ci_runs_python_314():
    text = CI.read_text(encoding="utf-8")
    assert 'python-version: "3.14"' in text
    assert 'python-version: "3.12"' not in text
    assert 'python-version: "3.10"' not in text
    assert text.count('python-version: "3.14"') == 2


def test_docs_claim_314_floor_not_310():
    for path in FLOOR_DOCS:
        text = path.read_text(encoding="utf-8")
        assert "3.14" in text, f"{path} must claim the 3.14 floor"
        assert "3.10+" not in text, f"{path} leftover 3.10 floor"
        assert "≥ 3.10" not in text, f"{path} leftover 3.10 floor"
        assert ">= 3.10" not in text, f"{path} leftover 3.10 floor"
