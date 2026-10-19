"""The client refuses swap HTML when it cannot check it.

These locks are the client half of the fail-closed branches. The server
removes the same vectors before the body is sent. The client is the
second layer.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest

_STATIC = (
    Path(__file__).resolve().parents[2] / "src" / "ux_channel" / "static" / "ux-channel.js"
)
_HTML = '<b onclick="window.PWN(1)">ok</b>'

_HARNESS = r"""
const fs = require("fs");
const vm = require("vm");
const mode = process.argv[2];
const src = fs.readFileSync(process.argv[3], "utf8");
function makeEl() {
  const el = { _html: "UNSET" };
  Object.defineProperty(el, "innerHTML", {
    get() { return el._html; },
    set(v) { el._html = String(v); },
  });
  return el;
}
const target = makeEl();
const document = {
  readyState: "loading",
  body: null,
  addEventListener() {},
  removeEventListener() {},
  dispatchEvent() { return true; },
  querySelector() { return target; },
  querySelectorAll() { return []; },
  createElement() { return makeEl(); },
  getElementById() { return null; },
};
const context = {
  console: { log() {}, warn() {}, error() {}, info() {} },
  document,
  CustomEvent: class CustomEvent {},
  setTimeout, clearTimeout, queueMicrotask, Promise, URL, TextEncoder,
  crypto: globalThis.crypto,
};
if (mode === "disagree") {
  function DOMParser() {}
  DOMParser.prototype.parseFromString = function () {
    const root = {
      attributes: [],
      querySelectorAll() { return []; },
      innerHTML: "",
    };
    return {
      getElementById() { return root; },
      body: { children: [root], firstElementChild: root },
    };
  };
  context.DOMParser = DOMParser;
}
context.window = context;
context.globalThis = context;
vm.createContext(context);
vm.runInContext(src, context, { filename: process.argv[3] });
context.uxChannel.applyResult({
  ok: true,
  ops: [{ op: "swap", target: "#t", html: process.argv[4], swap: "innerHTML" }],
}).then(() => {
  process.stdout.write(JSON.stringify({ html: target.innerHTML }));
}).catch((err) => {
  console.error(err && err.stack ? err.stack : String(err));
  process.exit(1);
});
"""


def _run(mode: str) -> str:
    binary = shutil.which("node")
    if not binary:
        pytest.skip("node is not installed")
    with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False) as fh:
        fh.write(_HARNESS)
        script = fh.name
    proc = subprocess.run(
        [binary, script, mode, str(_STATIC), _HTML],
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr
    return json.loads(proc.stdout)["html"]


def test_client_refuses_html_when_the_check_cannot_run() -> None:
    assert _run("missing") == ""


def test_client_refuses_html_when_the_parse_disagrees() -> None:
    assert _run("disagree") == ""
