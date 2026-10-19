"""Client and server share every drop-name list, not a 15-name sample.

``drop_names.json`` is the source. The scrubber's sets and both client
scripts copy ``content``, ``void``, ``animate``, ``animate_name``, and
``animate_url``.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from ux_channel.render.morph_policy import (
    _ANIMATE,
    _ANIMATE_NAME,
    _ANIMATE_URL,
    _DROP_CONTENT,
    _DROP_TAG,
)

_ROOT = Path(__file__).resolve().parents[2] / "src" / "ux_channel"
_NAMES = _ROOT / "render" / "drop_names.json"
_STATIC = _ROOT / "static" / "ux-channel.js"
_MARKERS = {
    "content": "DROP_CONTENT",
    "void": "DROP_VOID",
    "animate": "DROP_ANIMATE",
    "animate_name": "DROP_ANIMATE_NAME",
    "animate_url": "DROP_ANIMATE_URL",
}
_SERVER = {
    "content": _DROP_CONTENT,
    "void": _DROP_TAG,
    "animate": _ANIMATE,
    "animate_name": _ANIMATE_NAME,
    "animate_url": _ANIMATE_URL,
}


def _js_names(source: str, marker: str) -> set[str]:
    match = re.search(rf"var {marker} = (\[[\s\S]*?\]);", source)
    assert match, marker
    return set(json.loads(match.group(1)))


def test_client_and_server_share_the_full_drop_name_list() -> None:
    names = json.loads(_NAMES.read_text(encoding="utf-8"))
    assert set(names) == set(_MARKERS)
    union: set[str] = set()
    source = _STATIC.read_text(encoding="utf-8")
    minified = _STATIC.with_name("ux-channel.min.js").read_text(encoding="utf-8")
    for key, marker in _MARKERS.items():
        expected = set(names[key])
        union |= expected
        assert set(_SERVER[key]) == expected, key
        assert _js_names(source, marker) == expected, marker
        assert _js_names(minified, marker) == expected, marker + " min"
    assert len(union) > 15
