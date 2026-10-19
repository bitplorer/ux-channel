"""70 payloads through JSON, SSE, /push, /ws, and MCP, then headless Chrome.

The HTML Chrome applies is the HTML the route returned. A live handler is
a ``window.PWN`` call or an ``on*`` / ``javascript:`` attribute left after
the client applies that HTML. Strict must stay at 0. Policy off does not
strip swap markup, so its count is measured and reported.
"""

from __future__ import annotations

import importlib.util
import json
import shutil
import subprocess
import tempfile
import threading
import time
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from ux_channel import Channel, ChannelConfig, Intent, Result, swap

_SECRET = "chrome-payload-secret-32chars-min!"
_TOPIC = "board"
_MCP_TOPIC = "mcp.resource.board"
_STATIC_JS = (
    Path(__file__).resolve().parents[2] / "src" / "ux_channel" / "static" / "ux-channel.js"
)


def _payloads() -> list[str]:
    path = Path(__file__).with_name("test_strict_html_payloads.py")
    spec = importlib.util.spec_from_file_location("strict_html_payloads", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("payload module is missing")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return list(module.PAYLOADS)


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
    pytest.skip("chrome is not installed")
    return ""


def _boot(policy: str):
    app = FastAPI()
    cfg = ChannelConfig.development(
        secret=_SECRET,
        morph_html_policy=policy,
        observe="off",
        allow_memory_stores=True,
        mount_agent_mcp=True,
        agent_token="agent-tok",
        ws_require_origin=False,
    )
    ch = Channel.boot(app, config=cfg)
    holder = {"html": ""}

    @ch.on("Show.html")
    def _show() -> Result:
        return Result.success(swap("#slot", holder["html"], swap="innerHTML"))

    return app, ch, holder


def _kick(bus: object) -> None:
    subs = getattr(getattr(bus, "backend", None), "_subs", None)
    if not subs:
        return
    for queues in list(subs.values()):
        for q in list(queues):
            loop = getattr(q, "_loop", None)
            if loop is not None and not loop.is_closed():
                loop.call_soon_threadsafe(lambda: None)


def _html_of(body: object) -> str:
    if not isinstance(body, dict):
        return ""
    ops = body.get("ops")
    result = body.get("result")
    if not isinstance(ops, list) and isinstance(result, dict):
        ops = result.get("ops")
    if not isinstance(ops, list) or not ops or not isinstance(ops[0], dict):
        return ""
    return str(ops[0].get("html") or "")


def _json_html(client: TestClient, cap: str, holder: dict[str, str], html: str) -> str:
    holder["html"] = html
    response = client.post(
        "/ux-channel/action",
        json={"v": "1", "action": "Show.html", "args": {}, "cap": cap},
        headers={"Accept": "application/json"},
    )
    assert response.status_code == 200, response.text
    return _html_of(response.json())


def _sse_html(client: TestClient, cap: str, holder: dict[str, str], html: str) -> str:
    holder["html"] = html
    response = client.post(
        "/ux-channel/action",
        json={
            "v": "1",
            "action": "Show.html",
            "args": {},
            "cap": cap,
            "accept_stream": True,
        },
        headers={"Accept": "text/event-stream"},
    )
    assert response.status_code == 200, response.text
    data = ""
    for line in response.text.splitlines():
        if line.startswith("data: "):
            data = line[6:]
    assert data, response.text
    return _html_of(json.loads(data))


def _push_htmls(client: TestClient, ch: Channel, payloads: list[str]) -> list[str]:
    sink: list[str] = []
    ready = threading.Event()

    def _read() -> None:
        with client.stream("GET", f"/ux-channel/push/{_TOPIC}") as resp:
            assert resp.status_code == 200, resp.status_code
            ready.set()
            for chunk in resp.iter_text():
                sink.append(chunk)
                if "".join(sink).count("data: ") >= len(payloads):
                    return

    thread = threading.Thread(target=_read, daemon=True)
    thread.start()
    assert ready.wait(2), "push stream did not open"
    bus = ch.registry.push_bus
    for index, html in enumerate(payloads, start=1):
        ch.live.publish(_TOPIC, result=Result.success(swap("#slot", html, swap="innerHTML")))
        deadline = time.time() + 2
        while time.time() < deadline and "".join(sink).count("data: ") < index:
            _kick(bus)
            time.sleep(0.01)
    thread.join(2)
    text = "".join(sink)
    found = []
    for line in text.splitlines():
        if line.startswith("data: "):
            found.append(_html_of(json.loads(line[6:])))
    assert len(found) == len(payloads), (len(found), text[:400])
    return found


def _ws_htmls(client: TestClient, ch: Channel, payloads: list[str]) -> list[str]:
    found: list[str] = []
    bus = ch.registry.push_bus
    with client.websocket_connect(f"/ux-channel/ws?topics={_TOPIC}") as ws:
        assert ws.receive_json()["type"] == "hello"
        assert ws.receive_json()["type"] == "subscribed"
        for html in payloads:
            ch.live.publish(
                _TOPIC, result=Result.success(swap("#slot", html, swap="innerHTML"))
            )
            _kick(bus)
            box: dict[str, object] = {}

            def _recv() -> None:
                try:
                    box["msg"] = ws.receive_json()
                except Exception as exc:  # noqa: BLE001
                    box["err"] = exc

            thread = threading.Thread(target=_recv, daemon=True)
            thread.start()
            thread.join(2)
            assert "msg" in box, box
            found.append(_html_of(box["msg"]))
    assert len(found) == len(payloads)
    return found


def _mcp_htmls(client: TestClient, ch: Channel, payloads: list[str]) -> list[str]:
    sink: list[str] = []
    ready = threading.Event()

    def _read() -> None:
        with client.stream(
            "GET",
            "/ux-channel/mcp/resources/subscribe",
            params={"topic": _MCP_TOPIC},
            headers={"Authorization": "Bearer agent-tok"},
        ) as resp:
            assert resp.status_code == 200, resp.text
            ready.set()
            for chunk in resp.iter_text():
                sink.append(chunk)
                if "".join(sink).count("data: ") >= len(payloads) + 1:
                    return

    thread = threading.Thread(target=_read, daemon=True)
    thread.start()
    assert ready.wait(2), "MCP subscribe did not open"
    bus = ch.registry.push_bus
    for index, html in enumerate(payloads, start=1):
        ch.live.publish(
            _MCP_TOPIC, result=Result.success(swap("#slot", html, swap="innerHTML"))
        )
        # The hello event is the first data line.
        deadline = time.time() + 2
        while time.time() < deadline and "".join(sink).count("data: ") < index + 1:
            _kick(bus)
            time.sleep(0.01)
    thread.join(2)
    found = []
    for line in "".join(sink).splitlines():
        if not line.startswith("data: "):
            continue
        body = json.loads(line[6:])
        if body.get("event") == "subscribed":
            continue
        found.append(_html_of(body))
    assert len(found) == len(payloads), (len(found), "".join(sink)[:400])
    return found


def _collect(policy: str, payloads: list[str]) -> dict[str, list[str]]:
    app, ch, holder = _boot(policy)
    client = TestClient(app)
    cap = ch.registry.mint("Show.html", {})
    # Touch dispatch once so the cap path is the same one JSON uses.
    ch.registry.dispatch(Intent(action="Show.html", args={}, cap=cap))
    return {
        "json": [_json_html(client, cap, holder, html) for html in payloads],
        "sse": [_sse_html(client, cap, holder, html) for html in payloads],
        "push": _push_htmls(client, ch, payloads),
        "ws": _ws_htmls(client, ch, payloads),
        "mcp": _mcp_htmls(client, ch, payloads),
    }


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
      const name = String(a.name || "");
      const value = String(a.value || "");
      if (liveName(name) || /javascript:/i.test(value)) {{
        attrs.push(item.route + "#" + item.n + ":" + name);
      }}
    }}
  }});
}}
(async function () {{
  const attrs = [];
  let n = 0;
  for (const item of cases) {{
    const id = "slot" + (n++);
    const host = document.createElement("div");
    host.id = id;
    document.getElementById("stage").appendChild(host);
    const op = {{
      op: "swap",
      target: "#" + id,
      html: item.html,
      swap: "innerHTML"
    }};
    await window.uxChannel.applyResult({{ ok: true, ops: [op] }});
    scan(document.getElementById(id), item, attrs);
  }}
  setTimeout(function () {{
    document.getElementById("score").textContent = JSON.stringify({{
      hits: window.__hits,
      attrs: attrs
    }});
  }}, 50);
}})().catch(function (err) {{
  document.getElementById("score").textContent = JSON.stringify({{
    error: String(err && err.stack || err)
  }});
}});
</script>
</body></html>
"""


def _chrome_score(cases: list[dict]) -> dict:
    binary = _chrome_bin()
    js = _STATIC_JS.resolve().as_uri()
    encoded = json.dumps(cases).replace("<", "\\u003c")
    page = _PAGE.format(js=js, cases=encoded)
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "payloads.html"
        path.write_text(page, encoding="utf-8")
        profile = Path(tmp) / "profile"
        proc = subprocess.run(
            [
                "timeout",
                "25",
                binary,
                "--headless=new",
                "--no-sandbox",
                "--disable-gpu",
                f"--user-data-dir={profile}",
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
    rest = text[start + len(marker):]
    end = rest.find("</pre>")
    raw = rest[:end]
    assert raw and raw != "PENDING", raw
    score = json.loads(raw)
    assert "error" not in score, score
    return score


def test_chrome_payload_routes_have_no_live_handlers_under_strict() -> None:
    _chrome_bin()
    payloads = _payloads()
    assert len(payloads) == 70
    scores = {}
    for policy in ("off", "strict"):
        delivered = _collect(policy, payloads)
        cases = []
        for route, htmls in delivered.items():
            assert len(htmls) == 70, (policy, route, len(htmls))
            for number, html in enumerate(htmls, start=1):
                cases.append({"route": route, "n": number, "html": html})
        scores[policy] = _chrome_score(cases)
        print(
            f"CHROME {policy} hits={len(scores[policy]['hits'])} "
            f"attrs={len(scores[policy]['attrs'])}"
        )
    strict = scores["strict"]
    assert strict["hits"] == [], strict["hits"]
    assert strict["attrs"] == [], strict["attrs"][:20]
