"""The server removes always-refused vectors in both modes, on every transport.

Off mode still carries a ``<script>`` tag and the rest of the markup. A
non-JS consumer reads the same filtered body the browser would.
"""

from __future__ import annotations

import json
import threading
import time

import fakeredis
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from ux_channel import Channel, ChannelConfig, Result, swap
from ux_channel.redis_extra import RedisPushBus
from ux_channel.transport.stream import format_sse

_SECRET = "server-vector-secret-32chars-min!"
_TOPIC = "board"
_MCP_TOPIC = "mcp.resource.board"
_KEEP = "KEEP9"

_VECTORS: tuple[tuple[str, str, str], ...] = (
    ("on*", f'<b onclick="window.PWN(1)">t</b><i>{_KEEP}</i>', "onclick"),
    (
        "srcdoc",
        f'<iframe srcdoc="<script>alert(1)</script>"></iframe><i>{_KEEP}</i>',
        "srcdoc",
    ),
    (
        "javascript:",
        f'<a href="javascript:alert(1)">t</a><i>{_KEEP}</i>',
        "javascript:",
    ),
    (
        "vbscript:",
        f'<a href="vbscript:alert(1)">t</a><i>{_KEEP}</i>',
        "vbscript:",
    ),
    (
        "data:text/html",
        f'<a href="data:text/html,zzz">t</a><i>{_KEEP}</i>',
        "data:text/html",
    ),
    (
        "control-character URL",
        f'<a href="\x01javascript:alert(1)">t</a><i>{_KEEP}</i>',
        "javascript:",
    ),
)
_TRANSPORTS = ("json", "sse", "push", "ws", "mcp", "redis", "format_sse")
_SCRIPT = f"<script>alert(1)</script><b>{_KEEP}</b>"


def _boot(policy: str, *, redis: bool = False):
    app = FastAPI()
    cfg = ChannelConfig.development(
        secret=_SECRET,
        morph_html_policy=policy,
        observe="off",
        allow_memory_stores=True,
        require_cap=False,
        ws_require_origin=False,
        push_require_auth=False,
        mount_agent_mcp=True,
        agent_token="agent-tok",
    )
    ch = Channel.boot(app, config=cfg)
    holder = {"html": ""}

    @ch.on("Show.html")
    def _show() -> Result:
        return Result.success(swap("#t", holder["html"], swap="innerHTML"))

    fake = None
    if redis:
        fake = fakeredis.FakeRedis(decode_responses=True)
        bus = RedisPushBus(fake)
        bus.morph_html_policy = policy
        bus._policy_bound = True
        bus.navigate_allowed_hosts = ()
        ch.registry.push_bus = bus
        ch.push_bus = bus
    return app, ch, holder, fake


def _assert_clean(blob: str, needle: str, *, label: str) -> None:
    assert needle.lower() not in blob.lower(), label + " " + blob
    assert _KEEP in blob, label + " " + blob
    if needle == "javascript:":
        assert "\x01" not in blob, label
        assert "\\u0001" not in blob.lower(), label


def _json_blob(client: TestClient, holder: dict[str, str], html: str) -> str:
    holder["html"] = html
    response = client.post(
        "/ux-channel/action",
        json={"v": "1", "action": "Show.html", "args": {}},
        headers={"Accept": "application/json"},
    )
    assert response.status_code == 200, response.text
    return response.text


def _sse_blob(client: TestClient, holder: dict[str, str], html: str) -> str:
    holder["html"] = html
    response = client.post(
        "/ux-channel/action",
        json={"v": "1", "action": "Show.html", "args": {}, "accept_stream": True},
        headers={"Accept": "text/event-stream"},
    )
    assert response.status_code == 200, response.text
    return response.text


def _push_blob(client: TestClient, ch: Channel, html: str) -> str:
    sink: list[str] = []
    ready = threading.Event()

    def _read() -> None:
        with client.stream("GET", f"/ux-channel/push/{_TOPIC}") as resp:
            assert resp.status_code == 200, resp.status_code
            ready.set()
            for chunk in resp.iter_text():
                sink.append(chunk)
                if "data: " in "".join(sink):
                    return

    thread = threading.Thread(target=_read, daemon=True)
    thread.start()
    assert ready.wait(2), "push stream did not open"
    ch.live.publish(_TOPIC, result=Result.success(swap("#t", html, swap="innerHTML")))
    deadline = time.time() + 2
    while time.time() < deadline and "data: " not in "".join(sink):
        time.sleep(0.01)
    thread.join(0.2)
    return "".join(sink)


def _ws_blob(client: TestClient, ch: Channel, html: str) -> str:
    with client.websocket_connect(f"/ux-channel/ws?topics={_TOPIC}") as ws:
        assert ws.receive_json()["type"] == "hello"
        assert ws.receive_json()["type"] == "subscribed"
        ch.live.publish(_TOPIC, result=Result.success(swap("#t", html, swap="innerHTML")))
        return json.dumps(ws.receive_json())


def _mcp_blob(client: TestClient, ch: Channel, html: str) -> str:
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
                if "".join(sink).count("data: ") >= 2:
                    return

    thread = threading.Thread(target=_read, daemon=True)
    thread.start()
    assert ready.wait(2), "MCP subscribe did not open"
    ch.live.publish(
        _MCP_TOPIC, result=Result.success(swap("#t", html, swap="innerHTML"))
    )
    deadline = time.time() + 2
    while time.time() < deadline and "".join(sink).count("data: ") < 2:
        time.sleep(0.01)
    thread.join(0.2)
    return "".join(sink)


def _redis_blob(policy: str, html: str) -> str:
    app, ch, _holder, fake = _boot(policy, redis=True)
    assert fake is not None
    client = TestClient(app)
    sink: list[str] = []
    ready = threading.Event()
    bus = ch.registry.push_bus

    def _read() -> None:
        with client.stream("GET", f"/ux-channel/push/{_TOPIC}") as resp:
            assert resp.status_code == 200, resp.status_code
            ready.set()
            for chunk in resp.iter_text():
                sink.append(chunk)
                if "data: " in "".join(sink):
                    return

    thread = threading.Thread(target=_read, daemon=True)
    thread.start()
    assert ready.wait(2), "redis push stream did not open"
    deadline = time.time() + 1.5
    while time.time() < deadline and _TOPIC not in bus.backend._redis_topics:
        time.sleep(0.01)
    raw = {"ok": True, "ops": [swap("#t", html, swap="innerHTML")]}
    fake.publish(bus.backend._ch(_TOPIC), json.dumps(raw))
    deadline = time.time() + 2
    while time.time() < deadline and "data: " not in "".join(sink):
        time.sleep(0.02)
    thread.join(0.2)
    return "".join(sink)


def _format_blob(policy: str, html: str) -> str:
    body = Result.success(swap("#t", html, swap="innerHTML")).to_dict()
    return format_sse(body, policy=policy).decode("utf-8")


def _deliver(policy: str, transport: str, html: str) -> str:
    if transport == "format_sse":
        return _format_blob(policy, html)
    if transport == "redis":
        return _redis_blob(policy, html)
    app, ch, holder, _fake = _boot(policy)
    client = TestClient(app)
    if transport == "json":
        return _json_blob(client, holder, html)
    if transport == "sse":
        return _sse_blob(client, holder, html)
    if transport == "push":
        return _push_blob(client, ch, html)
    if transport == "ws":
        return _ws_blob(client, ch, html)
    if transport == "mcp":
        return _mcp_blob(client, ch, html)
    raise AssertionError(transport)


@pytest.mark.parametrize("policy", ("off", "strict"))
@pytest.mark.parametrize("transport", _TRANSPORTS)
@pytest.mark.parametrize(
    ("kind", "html", "needle"),
    _VECTORS,
    ids=[item[0] for item in _VECTORS],
)
def test_server_removes_refused_vector(
    policy: str, transport: str, kind: str, html: str, needle: str
) -> None:
    blob = _deliver(policy, transport, html)
    _assert_clean(blob, needle, label=f"{policy} {transport} {kind}")


def test_off_mode_still_carries_script() -> None:
    ops_off = _deliver("off", "format_sse", _SCRIPT)
    assert "<script" in ops_off.lower()
    assert _KEEP in ops_off
    ops_strict = _deliver("strict", "format_sse", _SCRIPT)
    assert "<script" not in ops_strict.lower()
    assert _KEEP in ops_strict


def test_mcp_raw_result_has_no_refused_vector() -> None:
    """A client that only reads the MCP JSON never sees an always-refused vector."""
    for policy in ("off", "strict"):
        for _kind, html, needle in _VECTORS:
            blob = _deliver(policy, "mcp", html)
            data = [
                line[6:]
                for line in blob.splitlines()
                if line.startswith("data: ") and "subscribed" not in line
            ]
            assert data, blob
            body = data[-1]
            _assert_clean(body, needle, label=policy + " mcp-raw")
