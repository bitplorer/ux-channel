"""The client set_attr drop list is the server's on* / srcdoc list.

``_event_or_srcdoc`` is the server rule. The browser applies the same
names and no others. A name that lands on one side and not the other
fails here, so the two checks cannot drift.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest

from ux_channel.security.security import _event_or_srcdoc

_STATIC = Path(__file__).resolve().parents[2] / "src" / "ux_channel" / "static"

# Probe the rule, including case, a leading space, a short "on", and a
# data-onclick that must stay. This is the list both sides are scored on.
_PROBE = (
    "onclick",
    "onerror",
    "ONLOAD",
    "on",
    "onx",
    " onclick",
    "srcdoc",
    "SRCDOC",
    " srcdoc",
    "data-onclick",
    "src",
    "href",
    "class",
    "onClick",
    "formaction",
)

_JS = r"""
const fs = require("fs");
const vm = require("vm");
const srcPath = process.argv[2];
const names = JSON.parse(process.argv[3]);

function el() {
  const attrs = Object.create(null);
  return {
    setAttribute(k, v) { attrs[k] = String(v); },
    getAttribute(k) {
      return Object.prototype.hasOwnProperty.call(attrs, k) ? attrs[k] : null;
    },
    removeAttribute(k) { delete attrs[k]; },
    hasAttribute(k) { return Object.prototype.hasOwnProperty.call(attrs, k); },
  };
}
const elements = Object.create(null);
const document = {
  readyState: "loading",
  body: null,
  addEventListener() {},
  removeEventListener() {},
  dispatchEvent() { return true; },
  querySelector(sel) {
    if (!elements[sel]) elements[sel] = el();
    return elements[sel];
  },
  querySelectorAll() { return []; },
  createElement() { return el(); },
  getElementById() { return null; },
};
const context = {
  console: { log() {}, warn() {}, error() {}, info() {} },
  document,
  CustomEvent: class CustomEvent {},
  setTimeout, clearTimeout, queueMicrotask, Promise, URL, TextEncoder,
  crypto: globalThis.crypto,
  btoa: (s) => Buffer.from(s, "binary").toString("base64"),
  atob: (s) => Buffer.from(s, "base64").toString("binary"),
};
context.window = context;
context.globalThis = context;
vm.createContext(context);
vm.runInContext(fs.readFileSync(srcPath, "utf8"), context, { filename: srcPath });

(async () => {
  const refused = [];
  for (const name of names) {
    const selector = "#n" + refused.length + names.indexOf(name);
    await context.uxChannel.applyResult({
      ok: true,
      ops: [{ op: "set_attr", target: selector, attrs: { [name]: "pwn" } }],
    });
    const node = document.querySelector(selector);
    if (node.getAttribute(name) === null) refused.push(name);
  }
  process.stdout.write(JSON.stringify(refused));
})().catch((err) => {
  console.error(err && err.stack ? err.stack : String(err));
  process.exit(1);
});
"""


def _client_refused(filename: str) -> set[str]:
    binary = shutil.which("node")
    if not binary:
        pytest.skip("node is not installed")
    with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False) as fh:
        fh.write(_JS)
        script = fh.name
    proc = subprocess.run(
        [binary, script, str(_STATIC / filename), json.dumps(list(_PROBE))],
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, f"{filename}\n{proc.stdout}\n{proc.stderr}"
    return set(json.loads(proc.stdout))


def test_client_on_srcdoc_drop_list_matches_server() -> None:
    server = {name for name in _PROBE if _event_or_srcdoc(name)}
    assert server, "the server drop list must not be empty"
    for filename in ("ux-channel.js", "ux-channel.min.js"):
        assert _client_refused(filename) == server, filename
