"""Scheme checks ignore C0, DEL, and whitespace the way a browser does.

html5lib rewrites U+0000 to U+FFFD before the scrubber runs. A consumer
that then strips controls still reads ``javascript:``. Both modes, on
JSON, SSE, push, WebSocket, and MCP, must refuse that URL.
"""

from __future__ import annotations

from html.parser import HTMLParser

import pytest

from gate.test_server_refused_vectors import _KEEP, _deliver

_TRANSPORTS = ("json", "sse", "push", "ws", "mcp")

# Leading and embedded noise in front of a script scheme.
_HREFS: tuple[tuple[str, str], ...] = (
    ("nul", "\x00javascript:alert(1)"),
    ("tab", "jav\tscript:alert(1)"),
    ("lf", "java\nscript:alert(1)"),
    ("cr", "java\rscript:alert(1)"),
    ("ff", "java\x0cscript:alert(1)"),
    ("u0001", "\x01javascript:alert(1)"),
    ("u001f", "\x1fjavascript:alert(1)"),
    ("del", "\x7fjavascript:alert(1)"),
    ("spaces", "  javascript:alert(1)"),
    ("embedded-nul", "java\x00script:alert(1)"),
    ("embedded-tab", "jav\tascript:alert(1)"),
    ("vbscript-nul", "\x00vbscript:alert(1)"),
    ("data-nul", "\x00data:text/html,zzz"),
)


def _page() -> str:
    parts = ["<div>"]
    for name, href in _HREFS:
        parts.append(f'<a id="{name}" href="{href}">t</a>')
    parts.append('<img src="\x00javascript:alert(1)">')
    parts.append('<form action="java\x00script:alert(1)"></form>')
    parts.append('<button formaction="\x00javascript:alert(1)">b</button>')
    parts.append('<svg><a xlink:href="\x00javascript:alert(1)">x</a></svg>')
    parts.append(
        '<svg><animate attributeName="href" values="java\x00script:alert(1)"></animate></svg>'
    )
    parts.append(
        '<svg><set attributeName="href" to="jav\tascript:alert(1)"></set></svg>'
    )
    parts.append(f"<i>{_KEEP}</i></div>")
    return "".join(parts)


def _flat(value: str) -> str:
    """Browser scheme scan: drop C0, DEL, U+FFFD, and whitespace."""
    kept: list[str] = []
    for ch in value:
        if ch == "\ufffd" or ch.isspace() or ord(ch) <= 0x1F or ord(ch) == 0x7F:
            continue
        kept.append(ch)
    return "".join(kept).lower()


class _ScriptUrls(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.bad: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        for name, value in attrs:
            if not value:
                continue
            flat = _flat(value)
            if (
                "javascript:" in flat
                or "vbscript:" in flat
                or "data:text/html" in flat
            ):
                self.bad.append(f"{tag} {name}={value!r}")


def _html_blobs(blob: str) -> list[str]:
    import json

    chunks: list[str] = []
    if "data: " in blob:
        for line in blob.splitlines():
            if line.startswith("data: "):
                chunks.append(line[6:])
    else:
        chunks.append(blob)
    found: list[str] = []

    def walk(node: object) -> None:
        if isinstance(node, dict):
            html = node.get("html")
            if isinstance(html, str):
                found.append(html)
            for child in node.values():
                walk(child)
        elif isinstance(node, list):
            for child in node:
                walk(child)

    for chunk in chunks:
        try:
            walk(json.loads(chunk))
        except json.JSONDecodeError:
            continue
    return found


def _assert_refused(blob: str, *, label: str) -> None:
    assert _KEEP in blob, label
    htmls = _html_blobs(blob)
    assert htmls, label + " " + blob[:500]
    for html in htmls:
        scanner = _ScriptUrls()
        scanner.feed(html)
        assert scanner.bad == [], label + " " + repr(scanner.bad)


@pytest.mark.parametrize("policy", ("off", "strict"))
@pytest.mark.parametrize("transport", _TRANSPORTS)
def test_url_scheme_strips_controls_before_the_check(policy: str, transport: str) -> None:
    blob = _deliver(policy, transport, _page())
    _assert_refused(blob, label=f"{policy} {transport}")
