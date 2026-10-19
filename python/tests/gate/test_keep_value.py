"""data-ux-keep-value survives a morph in the visitor's document.

jsdom runs under node whenever this gate test runs, including CI.
Chromium runs only when a Chrome or Chromium binary is on PATH.
The GitHub verify job does not install a browser, so that half skips.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
CASE_DIR = Path(__file__).resolve().parent / "js_keep_value"
DOCS = (
    ROOT / "CHANGELOG.md",
    ROOT / "python" / "docs" / "client" / "JS_RUNTIME.md",
    ROOT / "docs" / "reference" / "client-runtime.md",
)


def _ensure_js_deps() -> None:
    ready = (CASE_DIR / "node_modules" / "jsdom").is_dir() and (
        CASE_DIR / "node_modules" / "idiomorph"
    ).is_dir()
    if ready:
        return
    npm = shutil.which("npm")
    if not npm:
        pytest.skip("npm is not installed")
    proc = subprocess.run(
        [
            npm,
            "install",
            "--include=dev",
            "--ignore-scripts",
            "--no-audit",
            "--no-fund",
        ],
        cwd=CASE_DIR,
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        raise AssertionError(proc.stdout + proc.stderr)


def _run_cases() -> dict:
    node = shutil.which("node")
    if not node:
        pytest.skip("node is not installed")
    _ensure_js_deps()
    proc = subprocess.run(
        [node, "keep_value.test.mjs"],
        cwd=CASE_DIR,
        capture_output=True,
        text=True,
        check=False,
    )
    return {"code": proc.returncode, "out": proc.stdout, "err": proc.stderr}


def test_data_ux_keep_value_survives_morph() -> None:
    ran = _run_cases()
    assert ran["code"] == 0, ran["out"] + ran["err"]
    line = next(
        item
        for item in ran["out"].splitlines()
        if item.startswith("KEEP_VALUE_RESULT ")
    )
    payload = json.loads(line[len("KEEP_VALUE_RESULT ") :])
    assert payload["jsdom"]["ok"] is True
    assert payload["chrome"]["skipped"] is True or payload["chrome"]["ok"] is True


def test_keep_value_is_documented() -> None:
    for rel in DOCS:
        text = rel.read_text(encoding="utf-8")
        assert "data-ux-keep-value" in text, rel
        assert 'value=""' in text, rel
