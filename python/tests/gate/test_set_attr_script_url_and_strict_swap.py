"""H1 set_attr script-scheme URLs, H2 strict swap, and the H3 to_html pin.

Kept behavior at 83a580a is asserted and passes. The live H1 and H2 checks
are asserted as they must behave once closed, so they fail while the holes
are still open.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest
from fastapi import FastAPI

from ux_channel import (
    Channel,
    ChannelConfig,
    Intent,
    Result,
    esc,
    morph,
    set_attr,
    swap,
    toast,
)
from ux_channel.components.primitive import to_html
from ux_channel.render.morph_policy import apply_morph_policy

_SECRET = "h1h2-set-attr-secret-32chars-min!!"
_STATIC = Path(__file__).resolve().parents[2] / "src" / "ux_channel" / "static"
_LIVE_HREF = "javascript:window.PWN_ATTR=1;void 0"
_SWAP_HTML = '<img src="x" onerror="window.PWN_SWAP=1">'
_URL_ATTRS = ("href", "src", "action", "formaction", "xlink:href", "poster")
_SCRIPT_URLS = (
    _LIVE_HREF,
    "javascript:alert(1)",
    "JAVASCRIPT:alert(1)",
    "vbscript:msgbox(1)",
    "data:text/html,<script>alert(1)</script>",
    "data:text/html;base64,PHNjcmlwdD4=",
    "java script:alert(1)",
    "java\tscript:alert(1)",
    "java\nscript:alert(1)",
    "java\r\nscript:alert(1)",
    "java\x00script:alert(1)",
    "\x00javascript:alert(1)",
    "java\u200bscript:alert(1)",
    "java\u00adscript:alert(1)",
    "&#106;avascript:alert(1)",
    "&#x6A;avascript:alert(1)",
    "javascript&#58;alert(1)",
    "java&#115;cript:alert(1)",
    "java&#09;script:alert(1)",
    "javascript&colon;alert(1)",
    "&#38;#106;avascript:alert(1)",
    "//evil.example/a",
    "blob:https://example/uuid",
    "file:///etc/passwd",
)
_SAFE_HREFS = (
    "/ok",
    "./a",
    "https://example.com/a",
    "http://example.com/a",
    "mailto:a@b.c",
    "tel:+15551212",
    "#top",
    "?q=1",
    "",
    "  ",
)

_JS_HARNESS = r"""
const fs = require("fs");
const vm = require("vm");
const srcPath = process.argv[2];
const cases = JSON.parse(process.argv[3]);

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
  CustomEvent: class CustomEvent {
    constructor(type, init) {
      this.type = type;
      this.detail = init && init.detail;
    }
  },
  setTimeout, clearTimeout, queueMicrotask, Promise, URL, TextEncoder,
  crypto: globalThis.crypto,
  btoa: (s) => Buffer.from(s, "binary").toString("base64"),
  atob: (s) => Buffer.from(s, "base64").toString("binary"),
};
context.window = context;
context.globalThis = context;
vm.createContext(context);
vm.runInContext(fs.readFileSync(srcPath, "utf8"), context, { filename: srcPath });

async function apply(selector, attrs) {
  await context.uxChannel.applyResult({
    ok: true,
    ops: [{ op: "set_attr", target: selector, attrs }],
  });
  return document.querySelector(selector);
}

(async () => {
  for (const c of cases) {
    const node = document.querySelector(c.selector);
    if (c.prime) await apply(c.selector, c.prime);
    await apply(c.selector, c.attrs);
    const got = node.getAttribute(c.attr);
    if (got !== c.expect) {
      console.error(JSON.stringify({ file: srcPath, case: c, got }));
      process.exit(1);
    }
  }
})().catch((err) => {
  console.error(err && err.stack ? err.stack : String(err));
  process.exit(1);
});
"""


def _op_dicts(result: Result) -> list[dict]:
    out: list[dict] = []
    for op in result.ops:
        if hasattr(op, "to_dict"):
            out.append(op.to_dict())
        else:
            out.append(dict(op))
    return out


def _dispatch(policy: str, action: str, op: dict) -> list[dict]:
    app = FastAPI()
    cfg = ChannelConfig.development(
        secret=_SECRET,
        morph_html_policy=policy,
        observe="off",
        allow_memory_stores=True,
    )
    ch = Channel.boot(app, config=cfg)

    @ch.on(action)
    def _handler() -> Result:
        return Result.success(op)

    cap = ch.mint(action, {})
    result = ch.registry.dispatch(Intent(action=action, args={}, cap=cap))
    assert result.ok, result.error
    return _op_dicts(result)


def _set_attr_case(src: str) -> str:
    start = src.index('case "set_attr":')
    end = src.index('case "clear_errors":', start)
    return src[start:end]


def _run_client_cases(cases: list[dict]) -> None:
    binary = shutil.which("node")
    if not binary:
        pytest.skip("node is not installed")
    payload = json.dumps(cases)
    for name in ("ux-channel.js", "ux-channel.min.js"):
        with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False) as fh:
            fh.write(_JS_HARNESS)
            script_path = fh.name
        proc = subprocess.run(
            [binary, script_path, str(_STATIC / name), payload],
            capture_output=True,
            text=True,
            check=False,
        )
        assert proc.returncode == 0, f"{name}\n{proc.stdout}\n{proc.stderr}"


def test_set_attr_keeps_relative_https_and_non_url_attrs() -> None:
    for href in _SAFE_HREFS:
        op = set_attr("#link", {"href": href})
        assert op["op"] == "set_attr", href
        assert op["attrs"]["href"] == href
    op = set_attr(
        "#link",
        {
            "class": "javascript:alert(1)",
            "title": "vbscript:nope",
            "aria-invalid": "true",
            "data-href": "javascript:alert(1)",
            "data-src": "data:text/html,x",
            "disabled": True,
            "data-n": 3,
            "href": 1,
        },
    )
    assert op["op"] == "set_attr"
    assert op["attrs"]["class"] == "javascript:alert(1)"
    assert op["attrs"]["title"] == "vbscript:nope"
    assert op["attrs"]["aria-invalid"] == "true"
    assert op["attrs"]["data-href"] == "javascript:alert(1)"
    assert op["attrs"]["data-src"] == "data:text/html,x"
    assert op["attrs"]["disabled"] is True
    assert op["attrs"]["data-n"] == 3
    assert op["attrs"]["href"] == 1


def test_set_attr_refuses_script_schemes_on_url_attributes() -> None:
    for name in _URL_ATTRS:
        for url in _SCRIPT_URLS:
            op = set_attr("#t", {name: url, "class": "keep"})
            attrs = op.get("attrs") or {}
            assert attrs.get("class") == "keep", (name, url, op)
            assert attrs.get(name) != url, (name, url, op)
            blob = json.dumps(attrs).lower()
            assert "javascript:" not in blob, (name, url, op)
            assert "vbscript:" not in blob
            assert "data:text/html" not in blob


def test_set_attr_only_script_href_does_not_land() -> None:
    op = set_attr("#link", {"href": _LIVE_HREF})
    assert op["op"] == "noop", op
    assert (op.get("meta") or {}).get("reason") == "unsafe_href"
    assert "javascript:" not in json.dumps(op).lower()


def test_signed_set_attr_javascript_href_does_not_land() -> None:
    ops = _dispatch(
        "off",
        "probe.attr",
        set_attr("#link", {"href": _LIVE_HREF}),
    )
    assert ops
    assert all(op.get("op") != "set_attr" or "href" not in (op.get("attrs") or {}) for op in ops)
    assert "javascript:" not in json.dumps(ops).lower()


def test_signed_set_attr_relative_and_https_href_lands() -> None:
    for action, href in (("probe.rel", "/ok"), ("probe.https", "https://example.com/a")):
        ops = _dispatch("off", action, set_attr("#link", {"href": href}))
        assert ops[0]["op"] == "set_attr"
        assert ops[0]["attrs"]["href"] == href


def test_signed_raw_set_attr_dict_javascript_href_does_not_land() -> None:
    ops = _dispatch(
        "strict",
        "probe.raw",
        {"op": "set_attr", "target": "#link", "attrs": {"href": _LIVE_HREF, "class": "keep"}},
    )
    assert ops[0]["op"] == "set_attr"
    assert ops[0]["attrs"] == {"class": "keep"}
    assert "javascript:" not in json.dumps(ops).lower()


def test_off_policy_leaves_swap_and_morph_markup() -> None:
    ops = apply_morph_policy(
        [
            swap("#t", _SWAP_HTML, swap="innerHTML"),
            morph("#m", _SWAP_HTML),
        ],
        policy="off",
    )
    assert ops[0]["html"] == _SWAP_HTML
    assert ops[1]["html"] == _SWAP_HTML
    signed = _dispatch("off", "probe.swap_off", swap("#t", _SWAP_HTML, swap="innerHTML"))
    assert signed[0]["op"] == "swap"
    assert signed[0]["html"] == _SWAP_HTML


def test_strict_policy_still_strips_morph_and_toast() -> None:
    morph_ops = apply_morph_policy(
        [morph("#m", '<div id="m"><script>alert(1)</script><b>hi</b></div>')],
        policy="strict",
    )
    assert "<script" not in morph_ops[0]["html"].lower()
    assert "hi" in morph_ops[0]["html"]
    toast_ops = apply_morph_policy(
        [toast('<img src="x" onerror="alert(1)">')],
        policy="strict",
    )
    assert "onerror" not in str(toast_ops[0].get("message") or "").lower()


def test_strict_policy_strips_swap_onerror() -> None:
    ops = apply_morph_policy(
        [swap("#t", _SWAP_HTML, swap="innerHTML")],
        policy="strict",
    )
    assert "onerror" not in ops[0]["html"].lower()
    assert "<img" in ops[0]["html"].lower()
    signed = _dispatch("strict", "probe.swap", swap("#t", _SWAP_HTML, swap="innerHTML"))
    assert signed[0]["op"] == "swap"
    assert "onerror" not in signed[0]["html"].lower()
    assert signed[0]["swap"] == "innerHTML"


def test_to_html_str_and_bytes_return_markup_unchanged() -> None:
    raw = '<img src="x" onerror="window.PWN=1">'
    assert to_html(raw) == raw
    assert to_html(raw.encode()) == raw
    assert to_html(None) == ""
    escaped = esc(raw)
    assert escaped != raw
    assert "<img" not in escaped


def test_client_set_attr_case_checks_href_with_safe_href() -> None:
    for name in ("ux-channel.js", "ux-channel.min.js"):
        body = _set_attr_case((_STATIC / name).read_text())
        assert "safeHref(" in body
        assert "blocked unsafe set_attr" in body


def test_client_set_attr_keeps_relative_and_https() -> None:
    _run_client_cases(
        [
            {
                "selector": "#link",
                "attr": "href",
                "attrs": {"href": "/ok"},
                "expect": "/ok",
            },
            {
                "selector": "#link",
                "attr": "href",
                "attrs": {"href": "https://example.com/a"},
                "expect": "https://example.com/a",
            },
            {
                "selector": "#link",
                "attr": "href",
                "attrs": {"href": ""},
                "expect": "",
            },
            {
                "selector": "#link",
                "attr": "class",
                "prime": {"class": "before"},
                "attrs": {"class": "javascript:alert(1)"},
                "expect": "javascript:alert(1)",
            },
            {
                "selector": "#link",
                "attr": "href",
                "prime": {"href": "/ok"},
                "attrs": {"href": None},
                "expect": None,
            },
        ]
    )


def test_client_set_attr_refuses_script_scheme_urls() -> None:
    cases = []
    for url in (
        _LIVE_HREF,
        "vbscript:msgbox(1)",
        "data:text/html,<script>alert(1)</script>",
        "java\tscript:alert(1)",
        "java script:alert(1)",
        "java\u200bscript:alert(1)",
        "&#106;avascript:alert(1)",
        "javascript&#58;alert(1)",
        "javascript&colon;alert(1)",
        "&#38;#106;avascript:alert(1)",
        "//evil.example/a",
    ):
        cases.append(
            {
                "selector": "#link",
                "attr": "href",
                "prime": {"href": "/ok"},
                "attrs": {"href": url},
                "expect": "/ok",
            }
        )
    for name in ("src", "action", "formaction", "xlink:href"):
        cases.append(
            {
                "selector": "#" + name,
                "attr": name,
                "prime": {name: "/ok"},
                "attrs": {name: _LIVE_HREF},
                "expect": "/ok",
            }
        )
    _run_client_cases(cases)


def test_client_navigate_still_blocks_javascript() -> None:
    binary = shutil.which("node")
    if not binary:
        pytest.skip("node is not installed")
    script = r"""
const fs = require("fs");
const vm = require("vm");
const src = fs.readFileSync(process.argv[2], "utf8");
const start = src.indexOf("function safeHref");
const brace = src.indexOf("{", start);
let depth = 0;
let end = -1;
for (let n = brace; n < src.length; n++) {
  if (src[n] === "{") depth++;
  else if (src[n] === "}") {
    depth--;
    if (depth === 0) { end = n + 1; break; }
  }
}
const fn = src.slice(src.lastIndexOf("\n", start) + 1, end);
const safeHref = new Function(fn + "\nreturn safeHref;")();
const href = "javascript:window.PWN_ATTR=1;void 0";
if (safeHref(href) !== null) {
  console.error(safeHref(href));
  process.exit(1);
}
if (safeHref("/ok") !== "/ok") process.exit(1);
if (safeHref("https://example.com/a") !== "https://example.com/a") process.exit(1);
"""
    for name in ("ux-channel.js", "ux-channel.min.js"):
        with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False) as fh:
            fh.write(script)
            script_path = fh.name
        proc = subprocess.run(
            [binary, script_path, str(_STATIC / name)],
            capture_output=True,
            text=True,
            check=False,
        )
        assert proc.returncode == 0, f"{name}\n{proc.stdout}\n{proc.stderr}"
