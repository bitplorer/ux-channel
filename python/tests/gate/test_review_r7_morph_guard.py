"""Q85: the raw payload corpus goes through morph, and the client guard holds.

``applyMorph`` calls ``guardedHtml`` before insertion. Swap is a different
call. Both ``ux-channel.js`` and ``ux-channel.min.js`` must show 0 hits
and 0 dangerous attributes. The client script is the only filter: the
HTML is the raw corpus, not a server-stripped patch.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest

from gate.test_strict_html_payloads import PAYLOADS

_STATIC = (
    Path(__file__).resolve().parents[2] / "src" / "ux_channel" / "static"
)

_PAGE = """<!doctype html>
<html><body>
<div id="stage"></div>
<pre id="score">PENDING</pre>
<script src="{js}"></script>
<script>
const cases = {cases};
window.__hits = [];
window.PWN = function (n) {{ window.__hits.push(n); }};
function liveName(name) {{
  const token = String(name || "").replace(/^\\s+|\\s+$/g, "").toLowerCase();
  if (token === "srcdoc") return true;
  return token.length > 2 && token.indexOf("on") === 0;
}}
function scan(node, item, attrs) {{
  if (!node) return;
  const all = [node].concat(Array.from(node.querySelectorAll("*")));
  all.forEach(function (el) {{
    if (!el.attributes) return;
    for (let i = 0; i < el.attributes.length; i++) {{
      const a = el.attributes[i];
      const value = String(a.value || "");
      if (liveName(a.name) || /javascript:|vbscript:|data:\\s*text\\/html/i.test(value)) {{
        attrs.push(item.n + ":" + a.name);
      }}
    }}
  }});
}}
(async function () {{
  const attrs = [];
  let n = 0;
  for (const html of cases) {{
    const id = "slot" + (n++);
    const host = document.createElement("div");
    host.id = id;
    document.getElementById("stage").appendChild(host);
    await window.uxChannel.applyResult({{
      ok: true,
      ops: [{{ op: "morph", target: "#" + id, html: html }}]
    }});
    scan(document.getElementById("stage"), {{ n: n }}, attrs);
  }}
  document.getElementById("score").textContent = JSON.stringify({{
    hits: window.__hits,
    attrs: attrs
  }});
}})().catch(function (err) {{
  document.getElementById("score").textContent = JSON.stringify({{
    error: String(err && err.stack || err)
  }});
}});
</script>
</body></html>
"""


def _chrome_bin() -> str:
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
    if os.environ.get("UX_CHANNEL_REQUIRE_CHROME") == "1":
        pytest.fail("chrome is not installed")
    pytest.skip("chrome is not installed")
    return ""


@pytest.mark.parametrize("script", ("ux-channel.js", "ux-channel.min.js"))
def test_raw_corpus_through_morph_has_no_hits(script: str) -> None:
    binary = _chrome_bin()
    assert len(PAYLOADS) == 70
    js = (_STATIC / script).resolve().as_uri()
    encoded = json.dumps(list(PAYLOADS)).replace("<", "\\u003c")
    page = _PAGE.format(js=js, cases=encoded)
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "morph.html"
        path.write_text(page, encoding="utf-8")
        proc = subprocess.run(
            [
                "timeout",
                "30",
                binary,
                "--headless=new",
                "--no-sandbox",
                "--disable-gpu",
                f"--user-data-dir={Path(tmp) / 'profile'}",
                "--virtual-time-budget=8000",
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
    assert raw and raw != "PENDING", raw or text[-1500:]
    score = json.loads(raw)
    assert "error" not in score, score
    assert score["hits"] == [], score["hits"]
    assert score["attrs"] == [], score["attrs"][:20]
