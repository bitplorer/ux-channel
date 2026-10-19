"""Chrome: strict navigate tricks and svg/math style, on JSON and push.

Skips when Chrome is not installed. ``UX_CHANNEL_REQUIRE_CHROME=1`` fails
instead, so the gated CI job cannot pass with a skip.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
import threading
import time
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from ux_channel import Channel, ChannelConfig, Result

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


def _kick(bus: object) -> None:
    subs = getattr(getattr(bus, "backend", None), "_subs", None) or {}
    for queues in list(subs.values()):
        for q in list(queues):
            loop = getattr(q, "_loop", None)
            if loop is not None and not loop.is_closed():
                loop.call_soon_threadsafe(lambda: None)


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
        _kick(ch.registry.push_bus)
        time.sleep(0.01)
    thread.join(0.2)
    for line in "".join(sink).splitlines():
        if line.startswith("data: "):
            return json.loads(line[6:])["ops"][0]
    raise AssertionError("".join(sink))


def _score(cases: list[dict], script: Path | None = None) -> dict:
    binary = _chrome()
    encoded = json.dumps(cases).replace("<", "\\u003c")
    page = _PAGE.format(js=(script or _STATIC).resolve().as_uri(), cases=encoded)
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "nav.html"
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
