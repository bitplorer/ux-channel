"""Strict stripper must fail closed on the reviewer's payload list.

A fragment is kept only when the HTML parser pass and main's regex pass
both accept it. Nothing may come out with a live event handler or a
``javascript:`` URL. Every payload main's regex stripper already caught
must stay caught. An inline svg icon with no handlers is unchanged.
"""

from __future__ import annotations

import re
from html.parser import HTMLParser

import pytest

from ux_channel import swap
from ux_channel.render.morph_policy import apply_morph_policy, strip_dangerous_html
from ux_channel.security.security import _unsafe_url_attr

# window.PWN(n) marks execution. Indexes are 1-based, matching the review.
PAYLOADS = [
    '<svg/onload=window.PWN(1)>',
    '<svg onload=window.PWN(2)>',
    '<a href=javascript:window.PWN(3)>x</a>',
    '<a href="java&#115;cript:window.PWN(4)">x</a>',
    '<a href="&#x6A;avascript:window.PWN(5)">x</a>',
    '<a href="&#106;avascript:window.PWN(6)">x</a>',
    '<a href="java\tscript:window.PWN(7)">x</a>',
    '<a href="java\nscript:window.PWN(8)">x</a>',
    '<a href="jav&#x09;ascript:window.PWN(9)">x</a>',
    '<svg><script>window.PWN(10)</script></svg>',
    '<math><mtext><img src=x onerror=window.PWN(11)></mtext></math>',
    '<iframe srcdoc="<script>parent.PWN(12)</script>"></iframe>',
    '<!--><img src=x onerror=window.PWN(13)>-->',
    '<!-- --!><img src=x onerror=window.PWN(14)> -->',
    '<![CDATA[><img src=x onerror=window.PWN(15)>]]>',
    '<svg><![CDATA[><img src=x onerror=window.PWN(16)>]]></svg>',
    '<svg><style><img src=x onerror=window.PWN(17)></style></svg>',
    '<math><mtext><table><mglyph><style><img src=x onerror=window.PWN(18)>',
    '<noscript><p title="</noscript><img src=x onerror=window.PWN(19)>">',
    '<style><img src=x onerror=window.PWN(20)></style>',
    '<textarea><img src=x onerror=window.PWN(21)></textarea>',
    '<title><img src=x onerror=window.PWN(22)></title>',
    '<xmp><img src=x onerror=window.PWN(23)></xmp>',
    '<noembed><img src=x onerror=window.PWN(24)></noembed>',
    '<noframes><img src=x onerror=window.PWN(25)></noframes>',
    '<plaintext><img src=x onerror=window.PWN(26)>',
    '<svg><a xlink:href="javascript:window.PWN(27)"><text y=20>x</text></a></svg>',
    '<svg><animate attributeName=href values=javascript:window.PWN(28) /><a id=q><text>x</text></a></svg>',
    '<form><button formaction=javascript:window.PWN(29)>x</button></form>',
    '<img src=x onerror\x00=window.PWN(30)>',
    '<img src=x ONERROR=window.PWN(31)>',
    '<img/src=x/onerror=window.PWN(32)>',
    '<img src=x onerror =window.PWN(33)>',
    '<img src="x"onerror="window.PWN(34)">',
    '<img src=x on\terror=window.PWN(35)>',
    '<img src=`x` onerror=window.PWN(36)>',
    '<img src=x onerror="window.PWN(37)"//',
    '<a href="&#0000106;avascript:window.PWN(38)">x</a>',
    '<a href="javascript&colon;window.PWN(39)">x</a>',
    '<a href="&Tab;javascript:window.PWN(40)">x</a>',
    '<object data="javascript:window.PWN(41)"></object>',
    '<embed src="javascript:window.PWN(42)">',
    '<base href="javascript:/">',
    '<meta http-equiv=refresh content="0;url=javascript:window.PWN(44)">',
    '<script>window.PWN(45)</script><b>keep</b>',
    '<scr<script>ipt>window.PWN(46)</script>',
    '<iframe src="javascript:parent.PWN(47)"></iframe>',
    '<frameset onload=window.PWN(48)>',
    '<details open ontoggle=window.PWN(49)>',
    '<svg><set attributeName=onmouseover to=window.PWN(50) />',
    '<isindex action=javascript:window.PWN(51) type=image>',
    '<a href="java&#x0A;script:window.PWN(52)">x</a>',
    '<template><img src=x onerror=window.PWN(53)></template>',
    '<img src=x onerror=window.PWN(54) <b>',
    '<img src=x title="a" onerror="window.PWN(55)" alt=">">',
    '<div data-x="<img src=x onerror=window.PWN(56)>">ok</div>',
    '<custom-el onclick=window.PWN(57)>x</custom-el>',
    '<a href="  javascript:window.PWN(58)">x</a>',
    '<img src=x onerror=&#119;indow.PWN(59)>',
    '<svg><foreignObject><img src=x onerror=window.PWN(60)></foreignObject></svg>',
    '<math href="javascript:window.PWN(61)">CLICK</math>',
    '<svg><use href="data:image/svg+xml,<svg id=x xmlns=http://www.w3.org/2000/svg><image href=1 onerror=window.PWN(62) /></svg>#x" /></svg>',
    '<a href="data:text/html,<script>alert(63)</script>">x</a>',
    '<img srcset="x 1x, javascript:window.PWN(64) 2x">',
    '<input autofocus onfocus=window.PWN(65)>',
    '<select><style></select><img src=x onerror=window.PWN(66)></style>',
    '<svg></p><style><a id="</style><img src=1 onerror=window.PWN(67)>">',
    '<form><math><mtext></form><form><mglyph><style></math><img src onerror=window.PWN(68)>',
    '<a href="\x01javascript:window.PWN(69)">x</a>',
    '<img src=x onerror=window.PWN(70)//',
]

_ICON = (
    '<svg viewBox="0 0 24 24" aria-hidden="true">'
    '<path d="M12 2l4 8H8z"></path>'
    "</svg>"
)

# Main's regex stripper at 83a580a. Independent of the implementation so a
# payload it already removed cannot come back.
_SCRIPTISH = re.compile(
    r"<(script|iframe|object|embed|link|meta|base)\b[^>]*>.*?</\1\s*>",
    re.I | re.S,
)
_SCRIPTISH_EMPTY = re.compile(
    r"<(script|iframe|object|embed|link|meta|base)\b[^>]*/\s*>",
    re.I,
)
_ON_ATTR = re.compile(r"""\s+on[a-z]+\s*=\s*(['"]).*?\1""", re.I | re.S)
_ON_ATTR_UNQUOTED = re.compile(r"""\s+on[a-z]+\s*=\s*[^\s>]+""", re.I)
_JS_HREF = re.compile(
    r"""\s(href|src|xlink:href)\s*=\s*(['"])\s*javascript:[^'"]*\2""",
    re.I,
)


def _main_strip(html: str) -> str:
    if not html:
        return html
    out = _SCRIPTISH.sub("", html)
    out = _SCRIPTISH_EMPTY.sub("", out)
    out = _ON_ATTR.sub("", out)
    out = _ON_ATTR_UNQUOTED.sub("", out)
    out = _JS_HREF.sub("", out)
    return out


def _handler_name(name: str) -> bool:
    token = name.strip().lower()
    return len(token) > 2 and token.startswith("on") and token.isalpha()


def _js_url_value(name: str, value: str | None) -> bool:
    if value is None or value == "":
        return False
    if _unsafe_url_attr("href", value):
        return True
    if name.strip().lower() != "srcset":
        return False
    for part in value.split(","):
        bits = part.strip().split()
        if bits and _unsafe_url_attr("href", bits[0]):
            return True
    return False


class _LiveFinder(HTMLParser):
    """Browser-shaped scan: style is raw text only outside svg/math.

    ``html.parser`` treats style as raw text in every namespace, and it
    parses noscript as elements unless scripting is on. This finder does
    the opposite where the browser does, so a breakout still counts.
    """

    # style is intentionally absent: inside svg/math the browser parses it.
    CDATA_CONTENT_ELEMENTS = ("script", "xmp", "iframe", "noembed", "noframes")

    def __init__(self) -> None:
        super().__init__(convert_charrefs=False, scripting=True)
        self.vectors: list[str] = []
        self._stack: list[str] = []

    def _in_html_style(self) -> bool:
        if "style" not in self._stack:
            return False
        for tag in self._stack:
            if tag in ("svg", "math"):
                return False
            if tag == "style":
                return True
        return False

    def _note(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        # HTML-namespace style content is CSS text, not elements.
        if self._in_html_style() and tag != "style":
            return
        for name, value in attrs:
            if _handler_name(name):
                self.vectors.append(f"{tag} {name}")
            elif name.strip().lower() == "srcdoc" and value:
                self.vectors.append(f"{tag} srcdoc")
            elif _js_url_value(name, value):
                self.vectors.append(f"{tag} {name}={value}")
            elif (
                name.strip().lower() == "attributename"
                and value
                and _handler_name(value)
            ):
                self.vectors.append(f"{tag} attributeName={value}")

    def handle_starttag(
        self, tag: str, attrs: list[tuple[str, str | None]]
    ) -> None:
        self._note(tag, attrs)
        self._stack.append(tag)

    def handle_startendtag(
        self, tag: str, attrs: list[tuple[str, str | None]]
    ) -> None:
        self._note(tag, attrs)

    def handle_endtag(self, tag: str) -> None:
        if tag in self._stack:
            while self._stack:
                found = self._stack.pop()
                if found == tag:
                    break


def live_vectors(html: str) -> list[str]:
    finder = _LiveFinder()
    try:
        finder.feed(html)
        finder.close()
    except Exception:
        return ["parse-error"]
    return finder.vectors


@pytest.mark.parametrize(
    ("number", "payload"),
    list(enumerate(PAYLOADS, start=1)),
    ids=[f"p{n}" for n in range(1, len(PAYLOADS) + 1)],
)
def test_strict_stripper_payload_has_no_live_vector(
    number: int, payload: str
) -> None:
    out = strip_dangerous_html(payload)
    vectors = live_vectors(out)
    assert vectors == [], (number, out, vectors)
    main = _main_strip(payload)
    marker = f"window.PWN({number})"
    if marker not in main:
        assert marker not in out, (number, out)
    via = apply_morph_policy([swap("#t", payload)], policy="strict")
    assert live_vectors(str(via[0]["html"])) == [], (number, via)


@pytest.mark.parametrize("tag", ["xmp", "noembed", "noframes", "plaintext"])
@pytest.mark.parametrize("wrap", ["svg", "math"])
def test_foreign_raw_text_element_is_dropped(tag: str, wrap: str) -> None:
    html = f'<{wrap}><{tag}><img src="x" onerror="alert(1)"></{tag}></{wrap}>'
    out = strip_dangerous_html(html)
    assert tag not in out.lower(), out
    assert "onerror" not in out.lower(), out


def test_regex_disagreement_returns_nothing() -> None:
    """Raw text the regex would edit is refused, not half-stripped."""
    assert strip_dangerous_html("<textarea><script>alert(1)</script></textarea>") == ""
    assert strip_dangerous_html("<style>p onerror=alert(1)</style>") == ""


def test_parse_error_returns_nothing(monkeypatch: pytest.MonkeyPatch) -> None:
    def _boom(self, *args, **kwargs):
        raise RuntimeError("parse")

    monkeypatch.setattr("html5lib.HTMLParser.parseFragment", _boom)
    assert strip_dangerous_html("<b>ok</b>") == ""


def test_inline_svg_icon_without_handlers_is_unchanged() -> None:
    assert strip_dangerous_html(_ICON) == _ICON
    via = apply_morph_policy([swap("#icon", _ICON)], policy="strict")
    assert via[0]["html"] == _ICON
