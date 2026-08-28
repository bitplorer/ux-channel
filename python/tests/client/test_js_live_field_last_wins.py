"""Live input/change abort the in-flight Intent of the same control."""

from pathlib import Path

JS = Path(__file__).resolve().parents[2] / "src" / "ux_channel" / "static" / "ux-channel.js"


def _src() -> str:
    return JS.read_text(encoding="utf-8")


def test_live_fields_abort_inflight_instead_of_drop():
    src = _src()
    assert 'signal === "input" || signal === "change"' in src
    assert "holder.replaced" in src
    assert "inflight.abort" in src
    # Old policy dropped the later keystroke. That is the typeahead race.
    assert "if (signalInFlight[key]) return Promise.resolve();" not in src


def test_replaced_abort_is_silent():
    src = _src()
    compact = src.replace(" ", "").replace("\n", "")
    assert "meta:{replaced:true}" in compact
    assert "if (holder.replaced)" in src


def test_click_still_drops_while_inflight():
    src = _src()
    assert "if (inflight && !replace) return Promise.resolve();" in src
