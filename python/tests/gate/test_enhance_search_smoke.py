"""Flagship enhance_search — empty / error / pending / once-used + 390px."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
DEMO = ROOT / "demos" / "enhance_search" / "index.html"


def test_enhance_search_states_present():
    html = DEMO.read_text(encoding="utf-8")
    assert 'id="results"' in html
    # empty
    assert "empty" in html.lower() or "Start typing" in html or "Nothing yet" in html
    # error
    assert "error" in html.lower()
    # pending
    assert "uxc-pending" in html or "pending" in html.lower()
    # once-used / disabled
    assert "once" in html.lower() or "disabled" in html.lower() or "used" in html.lower()


def test_enhance_search_390px():
    html = DEMO.read_text(encoding="utf-8")
    assert "max-width" in html
    assert "box-sizing" in html or "overflow-x" in html
    assert "font-size: 16px" in html or "font-size:16px" in html
    # tap target
    assert "min-height: 44px" in html or "min-height:44px" in html or "padding: 12px" in html
