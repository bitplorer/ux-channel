"""Gate: the files that state the library version state the real one.

A fixed list, not a doc-wide regex: each listed file must mention the version
at least once, and every X.Y.Z in it must equal ``__version__`` unless it is
one of that file's known non-library strings below. Add a file here when a
doc starts stating the version; the release bump then cannot miss it.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

from ux_channel import __version__

REPO_ROOT = Path(__file__).resolve().parents[3]
SEMVER = re.compile(r"(?<![\w.])\d+\.\d+\.\d+(?!\w|\.\d)")

# file -> X.Y.Z strings in it that are not the library version
VERSION_FILES: dict[str, frozenset[str]] = {
    "README.md": frozenset({"0.2.0"}),  # cek-host / cek-surface floor
    "TERMINOLOGY.md": frozenset({"0.0.0"}),  # default bind host
    "python/VERSION": frozenset(),
    "python/docs/start/HOW_TO.md": frozenset(),  # title + runtime example
    "python/docs/start/API.md": frozenset(),  # __version__ comment
    "python/docs/start/DESIGN.md": frozenset(),
    "python/docs/start/GLOSSARY.md": frozenset(),
    "python/docs/start/COURSE.md": frozenset(),
    "python/docs/book/UX_CHANNEL_BOOK.md": frozenset(),
    "python/docs/asgi/SSE.md": frozenset(),
    "python/docs/asgi/WEBSOCKET.md": frozenset(),  # header + hello example
    "python/docs/FEATURES.md": frozenset(),
}

# Forms the review found a regex scan missing; pin that they stay covered.
REQUIRED_FORMS = {
    "python/docs/start/HOW_TO.md": rf"^# How to use ux-channel {re.escape(__version__)}$",
    "python/docs/start/API.md": rf'__version__,\s*#\s*"{re.escape(__version__)}"',
    "README.md": rf"^\| \*\*Version\*\* \| `{re.escape(__version__)}` \|",
}


def _text(rel: str) -> str:
    return (REPO_ROOT / rel).read_text(encoding="utf-8")


@pytest.mark.parametrize("rel", sorted(VERSION_FILES))
def test_listed_file_mentions_the_version(rel):
    mentions = [m for m in SEMVER.findall(_text(rel)) if m not in VERSION_FILES[rel]]
    assert mentions, f"{rel}: no library version mention (stale list?)"
    wrong = sorted({m for m in mentions if m != __version__})
    assert not wrong, f"{rel}: {wrong} != __version__ {__version__}"


@pytest.mark.parametrize("rel", sorted(REQUIRED_FORMS))
def test_required_version_forms_present(rel):
    assert re.search(REQUIRED_FORMS[rel], _text(rel), re.M), rel


def test_diagram_and_book_scripts_read_package_version():
    for rel in ("python/scripts/generate_diagrams.py", "python/scripts/build_uidchannel_book_pdf.py"):
        text = _text(rel)
        assert "_version.py" in text, rel
        assert not re.search(r'LIB_VER\s*=\s*"\d', text), rel
