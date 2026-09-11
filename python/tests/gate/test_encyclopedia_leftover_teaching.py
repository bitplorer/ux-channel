"""Encyclopedia leftover teaching for Cuts 1–2 (compose Cut 4 pattern).

Cuts 1–2 locked the tree. These pages must name leftovers as leftovers
and teach the live owners. Silence is a dual door.
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
HOST = ROOT / "python" / "src" / "ux_channel" / "host"

ENCYCLOPEDIA = (
    ROOT / "CHANGELOG.md",
    ROOT / "AGENTS.md",
    ROOT / "docs" / "INDEX.md",
    ROOT / "python" / "docs" / "FEATURES.md",
    ROOT / "python" / "ONTOLOGY.md",
    ROOT / "python" / "STABILITY.md",
    ROOT / "python" / "src" / "ux_channel" / "LAYERS.md",
)


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_encyclopedia_teaches_cut1_cut2_leftovers():
    """Live owners + leftover names present; retired doors not taught live."""
    features = _read(ROOT / "python" / "docs" / "FEATURES.md")
    ontology = _read(ROOT / "python" / "ONTOLOGY.md")
    changelog = _read(ROOT / "CHANGELOG.md")
    agents = _read(ROOT / "AGENTS.md")
    index = _read(ROOT / "docs" / "INDEX.md")
    layers = _read(ROOT / "python" / "src" / "ux_channel" / "LAYERS.md")
    stability = _read(ROOT / "python" / "STABILITY.md")

    for text in (features, changelog, agents, index, layers, stability):
        assert "ux_channel.devtools.cli:main" in text
        assert "ux_channel.cli:main" in text

    assert "scaffold/region_cli.py" in features
    assert "scaffold/region_cli.py" in ontology
    assert "host/region_cli.py" in features
    assert "host/region_cli.py" in ontology
    assert "host/region_cli.py" in agents

    for text in (features, ontology, agents, index, layers, changelog):
        assert "protocol.ops" in text
        assert "ops/" in text
        assert "enhance" in text.lower()

    assert "Leftover" in agents or "leftover" in agents
    assert "do not fashion" in features.lower() or "do not fashion" in agents.lower()


def test_ch_g0_placeholder_absent_and_taught():
    """Delete with absence lock. Mapping a 1-line stub would invent a product."""
    stub = HOST / "_ch_g0.py"
    assert not stub.exists(), f"leftover stub must stay deleted: {stub}"

    changelog = _read(ROOT / "CHANGELOG.md")
    agents = _read(ROOT / "AGENTS.md")
    features = _read(ROOT / "python" / "docs" / "FEATURES.md")
    for text in (changelog, agents, features):
        assert "_ch_g0" in text


def test_encyclopedia_files_exist_for_lock():
    missing = [str(p.relative_to(ROOT)) for p in ENCYCLOPEDIA if not p.is_file()]
    assert missing == [], f"encyclopedia lock targets missing: {missing}"


def test_encyclopedia_teaches_html_leftover_soft1():
    """Soft 1 leftover: channel does not own HTML. Live is ux-dom when present."""
    for path in ENCYCLOPEDIA:
        text = _read(path)
        assert "lower_html" in text, f"{path} must name leftover lower_html"
        assert "to_html" in text, f"{path} must name leftover to_html"
        assert "ux-dom" in text, f"{path} must teach live ux-dom owner"
        assert "html.escape" in text, f"{path} must teach stdlib fallback"
        lowered = text.replace("**", "")
        assert "does not own HTML" in lowered, f"{path} must teach leftover: channel does not own HTML"
