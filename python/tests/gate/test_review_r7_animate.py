"""SVG animate/set URL vectors are dropped in both modes, on every transport.

``attributeName`` of href, xlink:href, or on* drops the element. So does
``values``, ``to``, ``from``, or ``by`` when any ``;``-separated part is a
dangerous URL. Whitespace and case do not keep it.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest

from gate.test_review_r7_url_controls import _html_blobs
from gate.test_server_refused_vectors import _deliver
from ux_channel.render.morph_policy import strip_dangerous_html, strip_off_html

_KEEP = "KEEP-ANIM"
_TRANSPORTS = ("json", "sse", "push", "ws", "mcp")

# 28 is the existing animate href payload. 137–139 are the r7 additions.
_PAYLOADS: tuple[tuple[str, str, str], ...] = (
    (
        "28",
        '<svg><animate attributeName=href values=javascript:window.PWN(28) />'
        "<a><text>x</text></a></svg>",
        "animate",
    ),
    (
        "137",
        '<svg><set attributeName=" href " to="javascript:window.PWN(137)"></set></svg>',
        "set",
    ),
    (
        "138",
        '<svg><animate attributeName="href" values="1; javascript:window.PWN(138)">'
        "</animate></svg>",
        "animate",
    ),
    (
        "139",
        '<svg><animateTransform attributeName="XLINK:HREF" '
        'from="javascript:window.PWN(139)"></animateTransform></svg>',
        "animatetransform",
    ),
    (
        "139-motion",
        '<svg><animateMotion to="javascript:window.PWN(139)"></animateMotion>'
        "<rect></rect></svg>",
        "animatemotion",
    ),
    (
        "href-safe",
        '<svg><animate attributeName="href" values="https://app.test/ok"></animate>'
        "<rect></rect></svg>",
        "animate",
    ),
)


def _has_tag(html: str, tag: str) -> bool:
    return re.search(rf"<{tag}\b", html, re.I) is not None


def _flat(value: str) -> str:
    kept: list[str] = []
    for ch in value:
        if ch == "\ufffd" or ch.isspace() or ord(ch) <= 0x1F or ord(ch) == 0x7F:
            continue
        kept.append(ch)
    return "".join(kept).lower()


def _assert_dropped(out: str, tag: str, *, label: str) -> None:
    assert _KEEP in out, label + " " + out
    assert not _has_tag(out, tag), label + " " + out
    assert "javascript:" not in _flat(out), label + " " + out
    assert "window.pwn" not in _flat(out), label + " " + out


def _scrub(policy: str, html: str) -> str:
    fn = strip_dangerous_html if policy == "strict" else strip_off_html
    return fn(html + f"<b>{_KEEP}</b>")


@pytest.mark.parametrize("policy", ("off", "strict"))
@pytest.mark.parametrize(
    ("number", "html", "tag"),
    _PAYLOADS,
    ids=[item[0] for item in _PAYLOADS],
)
def test_animation_url_element_is_dropped(
    policy: str, number: str, html: str, tag: str
) -> None:
    _assert_dropped(_scrub(policy, html), tag, label=f"{policy} {number}")


@pytest.mark.parametrize("policy", ("off", "strict"))
@pytest.mark.parametrize("transport", _TRANSPORTS)
@pytest.mark.parametrize(
    ("number", "html", "tag"),
    _PAYLOADS,
    ids=[item[0] for item in _PAYLOADS],
)
def test_animation_url_element_is_dropped_on_the_wire(
    policy: str, transport: str, number: str, html: str, tag: str
) -> None:
    blob = _deliver(policy, transport, html + f"<b>{_KEEP}</b>")
    _assert_dropped(blob, tag, label=f"{policy} {transport} {number}")


def _chrome_bin() -> str:
    if os.environ.get("UX_CHANNEL_REQUIRE_CHROME") == "1":
        missing = "chrome is not installed"
    else:
        missing = ""
    for candidate in (
        "/opt/google/chrome/chrome",
        "/usr/bin/google-chrome",
        "/usr/bin/google-chrome-stable",
    ):
        if Path(candidate).is_file():
            return candidate
    found = shutil.which("google-chrome") or shutil.which("chrome")
    if found:
        return found
    if missing:
        pytest.fail(missing)
    pytest.skip("chrome is not installed")
    return ""


_CHROME_PAGE = """<!doctype html>
<html><body>
<div id="stage"></div>
<pre id="score">PENDING</pre>
<script>
const cases = {cases};
window.__hits = [];
window.PWN = function (n) {{ window.__hits.push(n); }};
function scan(node, item, attrs) {{
  if (!node) return;
  const all = [node].concat(Array.from(node.querySelectorAll("*")));
  all.forEach(function (el) {{
    if (!el.attributes) return;
    for (let i = 0; i < el.attributes.length; i++) {{
      const value = String(el.attributes[i].value || "");
      if (/javascript:/i.test(value)) attrs.push(item.id + ":" + el.attributes[i].name);
    }}
  }});
}}
const attrs = [];
cases.forEach(function (item) {{
  const host = document.createElement("div");
  host.id = item.id;
  document.getElementById("stage").appendChild(host);
  host.innerHTML = item.html;
  scan(host, item, attrs);
}});
document.getElementById("score").textContent = JSON.stringify({{
  hits: window.__hits,
  attrs: attrs
}});
</script>
</body></html>
"""


def test_chrome_animate_payloads_do_not_run_with_the_client_guard_off() -> None:
    """Server HTML is inserted with innerHTML. The client guard is not loaded."""
    binary = _chrome_bin()
    cases = []
    for policy in ("off", "strict"):
        for transport in ("json", "sse", "push", "ws"):
            for number, html, _tag in _PAYLOADS:
                blob = _deliver(policy, transport, html + f"<b>{_KEEP}</b>")
                htmls = _html_blobs(blob)
                assert htmls, (policy, transport, number)
                cases.append(
                    {
                        "id": f"{policy}-{transport}-{number}",
                        "html": htmls[-1],
                    }
                )
    encoded = json.dumps(cases).replace("<", "\\u003c")
    page = _CHROME_PAGE.format(cases=encoded)
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "animate.html"
        path.write_text(page, encoding="utf-8")
        proc = subprocess.run(
            [
                "timeout",
                "25",
                binary,
                "--headless=new",
                "--no-sandbox",
                "--disable-gpu",
                f"--user-data-dir={Path(tmp) / 'profile'}",
                "--virtual-time-budget=4000",
                "--dump-dom",
                path.as_uri(),
            ],
            capture_output=True,
            text=True,
            check=False,
        )
    text = proc.stdout
    marker = '<pre id="score">'
    start = text.find(marker)
    assert start >= 0, text[-1500:]
    raw = text[start + len(marker) : text.find("</pre>", start)]
    assert raw and raw != "PENDING", raw
    score = json.loads(raw)
    assert score["hits"] == [], score["hits"]
    assert score["attrs"] == [], score["attrs"][:20]
