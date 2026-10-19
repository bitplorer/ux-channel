"""Q20: client safeHref refuses an authority that starts with ``@``.

The client is loaded in jsdom (``ux-channel.js`` and ``ux-channel.min.js``).
Chrome runs the same two empty-``@`` navigates in
``test_chrome_navigate_style.py``, which the gated Chrome job already
collects.

``https://user@evil.test/`` does not start with ``@``. ``safeHref`` returns
that string, so dropping the empty-``@`` check does not change it.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

_STATIC = (
    Path(__file__).resolve().parents[2] / "src" / "ux_channel" / "static"
)
_JSDOM_ROOT = Path(__file__).resolve().parent / "js_keep_value"
_SCRIPTS = ("ux-channel.js", "ux-channel.min.js")

# (href, safeHref result, loaded client warns "blocked unsafe navigate")
_CASES = (
    ("https://@evil.test/", None, True),
    ("https://@app.test@evil.test/", None, True),
    ("https://user@evil.test/", "https://user@evil.test/", False),
)

_RUNNER = r"""
const { JSDOM } = require(process.argv[1]);
const fs = require("fs");
const src = fs.readFileSync(process.argv[2], "utf8");
const hrefs = JSON.parse(process.argv[3]);

function extractSafeHref(source) {
  const start = source.indexOf("function safeHref");
  if (start < 0) throw new Error("missing safeHref");
  const brace = source.indexOf("{", start);
  let depth = 0;
  let end = -1;
  for (let n = brace; n < source.length; n++) {
    if (source[n] === "{") depth++;
    else if (source[n] === "}") {
      depth--;
      if (depth === 0) { end = n + 1; break; }
    }
  }
  if (end < 0) throw new Error("safeHref did not close");
  const fn = source.slice(source.lastIndexOf("\n", start) + 1, end);
  return new Function(fn + "\nreturn safeHref;")();
}

const safeHref = extractSafeHref(src);
const dom = new JSDOM("<!doctype html><html><body></body></html>", {
  url: "https://app.test/start",
  runScripts: "dangerously",
});
const win = dom.window;
const warns = [];
const origWarn = win.console.warn.bind(win.console);
win.console.warn = function (...args) {
  warns.push(args.map((item) => String(item)).join(" "));
  return origWarn(...args);
};
win.eval(src);
if (!win.uxChannel || typeof win.uxChannel.applyResult !== "function") {
  console.error("client did not load");
  process.exit(1);
}

(async function () {
  const out = [];
  for (const href of hrefs) {
    const mark = warns.length;
    await Promise.race([
      win.uxChannel.applyResult({ ok: true, ops: [{ op: "navigate", href: href }] }),
      new Promise(function (resolve) { setTimeout(resolve, 40); }),
    ]);
    const fresh = warns.slice(mark).join("\n");
    out.push({
      href: href,
      safeHref: safeHref(href),
      blocked: fresh.indexOf("blocked unsafe navigate") !== -1,
    });
  }
  process.stdout.write(JSON.stringify(out));
  dom.window.close();
})().catch(function (err) {
  console.error(err && err.stack || err);
  process.exit(1);
});
"""


def _jsdom_api() -> Path:
    entry = _JSDOM_ROOT / "node_modules" / "jsdom" / "lib" / "api.js"
    if entry.is_file():
        return entry
    npm = shutil.which("npm")
    if shutil.which("node") is None or npm is None:
        pytest.skip("node is not installed")
    proc = subprocess.run(
        [npm, "ci", "--ignore-scripts", "--no-audit", "--no-fund"],
        cwd=_JSDOM_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert entry.is_file()
    return entry


def _load(script_name: str) -> list[dict]:
    node = shutil.which("node")
    if node is None:
        pytest.skip("node is not installed")
    api = _jsdom_api()
    hrefs = [item[0] for item in _CASES]
    proc = subprocess.run(
        [node, "-e", _RUNNER, str(api), str(_STATIC / script_name), json.dumps(hrefs)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    return json.loads(proc.stdout)


@pytest.mark.parametrize("script_name", _SCRIPTS)
def test_loaded_client_safe_href_refuses_empty_at(script_name: str) -> None:
    rows = {item["href"]: item for item in _load(script_name)}
    for href, expected, blocked in _CASES:
        got = rows[href]
        assert got["safeHref"] == expected, (script_name, href, got)
        assert got["blocked"] is blocked, (script_name, href, got)
