"""Chrome: strict navigate tricks and svg/math style, on JSON and push.

Skips when Chrome is not installed. ``UX_CHANNEL_REQUIRE_CHROME=1`` fails
instead, so the gated CI job cannot pass with a skip.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import tempfile
import threading
import time
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from gate.test_review_r7_navigate_mutants import _TRANSPORTS, _deliver
from ux_channel import Channel, ChannelConfig, Result
from ux_channel.security.security import filter_outbound_ops

_SECRET = "chrome-nav-secret-32chars-minimum!"
_TOPIC = "board"
_STATIC = (
    Path(__file__).resolve().parents[2] / "src" / "ux_channel" / "static" / "ux-channel.js"
)
_TRICKS = (
    "https://evil.test\\@app.test/",
    "https:\\\\evil.test/",
    "https:/\\evil.test/",
    "https:///evil.test/",
    "http:evil.test/",
    "https://evil.test\\.app.test/",
)
_STYLE = (
    "<svg><style>.x{color:red}</style><rect id='r'></rect></svg>"
    "<math><style>.y{color:blue}</style><mi>a</mi></math>"
)

_PAGE = """<!doctype html>
<html><body>
<div id="stage"></div>
<pre id="score">PENDING</pre>
<script src="{js}"></script>
<script>
const cases = {cases};
const start = location.href;
(async function () {{
  const blocked = [];
  for (const item of cases) {{
    const before = location.href;
    // applyResult never settles a navigate op, blocked or not.
    await Promise.race([
      window.uxChannel.applyResult({{ ok: true, ops: [item.op] }}),
      new Promise(function (resolve) {{ setTimeout(resolve, 200); }})
    ]);
    blocked.push({{
      route: item.route,
      href: item.href || "",
      stayed: location.href === before
    }});
    if (location.href !== before) break;
  }}
  const styles = document.querySelectorAll("svg style, math style").length;
  document.getElementById("score").textContent = JSON.stringify({{
    blocked: blocked,
    styles: styles,
    left: location.href !== start
  }});
}})().catch(function (err) {{
  document.getElementById("score").textContent = JSON.stringify({{
    error: String(err && err.stack || err)
  }});
}});
</script>
</body></html>
"""


def _chrome() -> str:
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


def _boot():
    app = FastAPI()
    cfg = ChannelConfig.development(
        secret=_SECRET,
        morph_html_policy="strict",
        observe="off",
        allow_memory_stores=True,
        require_cap=False,
        push_require_auth=False,
    )
    ch = Channel.boot(app, config=cfg)
    holder = {"href": "/ok", "html": _STYLE}

    @ch.on("Go.there")
    def _go() -> Result:
        return Result.success({"op": "navigate", "href": holder["href"]})

    @ch.on("Show.html")
    def _show() -> Result:
        return Result.success(
            {"op": "swap", "target": "#stage", "html": holder["html"], "swap": "innerHTML"}
        )

    return app, ch, holder


def _json_op(client: TestClient, holder: dict[str, str], href: str) -> dict:
    holder["href"] = href
    response = client.post(
        "/ux-channel/action",
        json={"v": "1", "action": "Go.there", "args": {}},
        headers={"Host": "app.test"},
    )
    assert response.status_code == 200, response.text
    return response.json()["ops"][0]


def _push_op(client: TestClient, ch: Channel, href: str) -> dict:
    sink: list[str] = []
    ready = threading.Event()

    def _read() -> None:
        with client.stream("GET", f"/ux-channel/push/{_TOPIC}") as resp:
            assert resp.status_code == 200
            ready.set()
            for chunk in resp.iter_text():
                sink.append(chunk)
                if "data: " in "".join(sink):
                    return

    thread = threading.Thread(target=_read, daemon=True)
    thread.start()
    assert ready.wait(2)
    ch.live.publish(
        _TOPIC, result=Result.success({"op": "navigate", "href": href})
    )
    deadline = time.time() + 2
    while time.time() < deadline and "data: " not in "".join(sink):
        time.sleep(0.01)
    thread.join(0.2)
    for line in "".join(sink).splitlines():
        if line.startswith("data: "):
            return json.loads(line[6:])["ops"][0]
    raise AssertionError("".join(sink))


def _dump_dom(page: str, *, timeout_s: str = "40") -> str:
    """Headless dump. One retry when Chrome exits with no document.

    A busy runner can kill the first launch before ``--dump-dom`` writes.
    A navigation still returns a document, so the retry does not hide one.
    """
    binary = _chrome()
    last_err = ""
    text = ""
    for _attempt in range(2):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "nav.html"
            path.write_text(page, encoding="utf-8")
            proc = subprocess.run(
                [
                    "timeout",
                    timeout_s,
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
        last_err = proc.stderr
        if text.strip():
            return text
    assert text.strip(), last_err[-1500:]
    return text


def _score(cases: list[dict], script: Path | None = None) -> dict:
    encoded = json.dumps(cases).replace("<", "\\u003c")
    page = _PAGE.format(js=(script or _STATIC).resolve().as_uri(), cases=encoded)
    text = _dump_dom(page)
    marker = '<pre id="score">'
    start = text.find(marker)
    assert start >= 0, text[-1500:]
    raw = text[start + len(marker):]
    raw = raw[: raw.find("</pre>")]
    score = json.loads(raw)
    assert "error" not in score, score
    return score


def test_chrome_json_and_push_block_open_redirects_and_svg_style() -> None:
    app, ch, holder = _boot()
    client = TestClient(app, base_url="http://app.test")
    cases = []
    for href in _TRICKS:
        for route, op in (
            ("json", _json_op(client, holder, href)),
            ("push", _push_op(client, ch, href)),
        ):
            assert op["op"] == "noop", route + " " + href
            assert "evil.test" not in json.dumps(op)
            cases.append({"route": route, "href": href, "op": op})
            cases.append(
                {
                    "route": route + "-client",
                    "href": href,
                    "op": {"op": "navigate", "href": href},
                }
            )
    style = client.post(
        "/ux-channel/action",
        json={"v": "1", "action": "Show.html", "args": {}},
    ).json()["ops"][0]
    assert "<style" not in style["html"].lower()
    cases.append({"route": "json-style", "href": "", "op": style})
    score = _score(cases)
    assert score["left"] is False
    assert score["styles"] == 0
    for item in score["blocked"]:
        assert item["stayed"] is True, item


# Authority that starts with "@" is an empty userinfo. Chrome reads the host
# after that "@" (https://@evil.test/ is evil.test). A named user is not this
# check: safeHref returns https://user@evil.test/ unchanged.
_EMPTY_AT = (
    "https://@evil.test/",
    "https://@app.test@evil.test/",
)


@pytest.mark.parametrize("script_name", ("ux-channel.js", "ux-channel.min.js"))
def test_chrome_safe_href_blocks_empty_at_userinfo(script_name: str) -> None:
    script = _STATIC.parent / script_name
    cases = [
        {
            "route": href,
            "href": href,
            "op": {"op": "navigate", "href": href},
        }
        for href in _EMPTY_AT
    ]
    score = _score(cases, script)
    assert score["left"] is False, (script_name, score)
    assert len(score["blocked"]) == len(_EMPTY_AT), (script_name, score)
    for item in score["blocked"]:
        assert item["stayed"] is True, (script_name, item)


# The host is the label after the last "@". These three must get the same
# keep/drop verdict as the bare host, on the client and on every server mode
# the suite already runs. An empty "@" is the exception pinned below.
_BARE = "https://evil.test/"
_EMPTY = "https://@evil.test/"
_USERINFO = (
    "https://user@evil.test/",
    "https://app.test@evil.test/",
    _EMPTY,
)
_FILTER_MODES = {
    "off": {"policy": "off"},
    "off-app": {"policy": "off", "allowed_hosts": ("app.test",)},
    "strict-app": {"policy": "strict", "allowed_hosts": ("app.test",)},
    "strict-app-origin": {
        "policy": "strict",
        "allowed_hosts": ("app.test",),
        "origin_host": "app.test",
    },
    # Q7: evil.test itself is allowed, and an empty "@" is still refused.
    "strict-evil": {
        "policy": "strict",
        "allowed_hosts": ("evil.test",),
        "origin_host": "evil.test",
    },
}
_JSDOM_ROOT = Path(__file__).resolve().parent / "js_keep_value"
_JS_CACHE: dict[str, dict[str, dict]] = {}
_CHROME_CACHE: dict[tuple[str, str], tuple[str, str]] = {}
_TITLE = re.compile(r"<title>([^<]*)</title>", re.IGNORECASE)
_JS_RUNNER = r"""
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
win.console.warn = function (...args) {
  warns.push(args.map((item) => String(item)).join(" "));
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


def _slug(href: str) -> str:
    return {
        "https://user@evil.test/": "user",
        "https://app.test@evil.test/": "app",
        _EMPTY: "empty",
    }[href]


def _userinfo_cases():
    for mode in (*_FILTER_MODES, *_TRANSPORTS):
        for href in _USERINFO:
            yield pytest.param(
                "server", mode, href, id=f"server-{mode}-{_slug(href)}"
            )
    for script in ("ux-channel.js", "ux-channel.min.js"):
        for href in _USERINFO:
            yield pytest.param("js", script, href, id=f"js-{script}-{_slug(href)}")
            yield pytest.param(
                "chrome", script, href, id=f"chrome-{script}-{_slug(href)}"
            )


def _browser_host(href: str) -> str:
    """Host a browser navigates: the label after the last ``@``, without a port."""
    authority = href.split("://", 1)[1].split("/", 1)[0].split("?", 1)[0].split("#", 1)[0]
    if "@" in authority:
        authority = authority.rsplit("@", 1)[1]
    if authority.startswith("["):
        end = authority.find("]")
        return authority[1:end].lower() if end > 1 else ""
    return authority.split(":", 1)[0].lower()


def _kept(href: str) -> tuple[str, str]:
    return ("keep", _browser_host(href))


def _server_verdict(mode: str, href: str) -> tuple[str, str]:
    if mode in _FILTER_MODES:
        op = filter_outbound_ops(
            [{"op": "navigate", "href": href}],
            **_FILTER_MODES[mode],
        )[0]
    else:
        op = _deliver(
            mode,
            href,
            hosts=("app.test",),
            request_host="app.test",
        )
    if op.get("op") != "navigate":
        return ("drop", "")
    return _kept(str(op["href"]))


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


def _js_table(script_name: str) -> dict[str, dict]:
    cached = _JS_CACHE.get(script_name)
    if cached is not None:
        return cached
    node = shutil.which("node")
    if node is None:
        pytest.skip("node is not installed")
    hrefs = [_BARE, *_USERINFO]
    proc = subprocess.run(
        [
            node,
            "-e",
            _JS_RUNNER,
            str(_jsdom_api()),
            str(_STATIC.parent / script_name),
            json.dumps(hrefs),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    table = {row["href"]: row for row in json.loads(proc.stdout)}
    _JS_CACHE[script_name] = table
    return table


def _js_verdict(script_name: str, href: str) -> tuple[str, str]:
    row = _js_table(script_name)[href]
    value = row["safeHref"]
    assert (value is None) == bool(row["blocked"]), (script_name, href, row)
    if value is None:
        return ("drop", "")
    return _kept(str(value))


def _chrome_verdict(script_name: str, href: str) -> tuple[str, str]:
    key = (script_name, href)
    cached = _CHROME_CACHE.get(key)
    if cached is not None:
        return cached
    script = (_STATIC.parent / script_name).resolve().as_uri()
    page = f"""<!doctype html><html><body>
<pre id="score">PENDING</pre>
<script src="{script}"></script>
<script>
const href = {json.dumps(href)};
const before = location.href;
Promise.race([
  window.uxChannel.applyResult({{ok:true, ops:[{{op:"navigate", href:href}}]}}),
  new Promise(function (resolve) {{ setTimeout(resolve, 200); }})
]).then(function () {{
  document.getElementById("score").textContent = JSON.stringify({{
    stayed: location.href === before
  }});
}});
</script></body></html>"""
    text = _dump_dom(page)
    marker = '<pre id="score">'
    if marker in text and '"stayed":true' in text:
        verdict = ("drop", "")
    else:
        found = _TITLE.search(text)
        assert found, text[-500:]
        verdict = ("keep", found.group(1).strip().lower())
    _CHROME_CACHE[key] = verdict
    return verdict


def _verdict(surface: str, mode: str, href: str) -> tuple[str, str]:
    if surface == "server":
        return _server_verdict(mode, href)
    if surface == "js":
        return _js_verdict(mode, href)
    if surface == "chrome":
        return _chrome_verdict(mode, href)
    raise AssertionError(surface)


def _empty_at_is_stricter(surface: str, mode: str) -> bool:
    """Empty ``@`` is dropped while ``https://evil.test/`` is kept.

    The client always drops it. Strict drops it even when ``evil.test`` is
    the allowed host. Off keeps it, the same verdict as the bare host.
    """
    if surface != "server":
        return True
    return mode == "strict-evil"


@pytest.mark.parametrize(("surface", "mode", "href"), _userinfo_cases())
def test_userinfo_verdict_matches_the_bare_host(
    surface: str, mode: str, href: str
) -> None:
    """Userinfo does not choose the host. The label after the last ``@`` does."""
    got = _verdict(surface, mode, href)
    bare = _verdict(surface, mode, _BARE)
    if href == _EMPTY and _empty_at_is_stricter(surface, mode):
        assert got == ("drop", ""), (surface, mode, got, bare)
        assert bare == ("keep", "evil.test"), (surface, mode, bare)
        return
    assert got == bare, (surface, mode, href, got, bare)
