"""Strict navigate pins for the r6 same-origin mutants.

Each case goes out as a navigate op on the transports that apply that
rule. JSON and SSE actions see the request Host. Push, WebSocket, MCP,
and Redis publish with no request, so only the allowlist can keep an
absolute URL. ``format_sse`` takes the host when the caller passes one.

``navigate()`` runs ``safe_href`` first and drops Cf/Co/Cn characters.
Q2 is the outbound check on a navigate op that still carries them.
"""

from __future__ import annotations

import json
import threading
import time

import fakeredis
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from ux_channel import Channel, ChannelConfig, Result, navigate
from ux_channel.redis_extra import RedisPushBus
from ux_channel.transport.stream import format_sse

_SECRET = "navigate-mutant-secret-32chars!!"
_TOPIC = "board"
_MCP_TOPIC = "mcp.resource.board"
_TRANSPORTS = ("json", "sse", "push", "ws", "mcp", "redis", "format_sse")
_NO_REQUEST = ("push", "ws", "mcp", "redis", "format_sse")
_WITH_HOST = ("json", "sse", "format_sse")

# Cf, Co, and Cn. Cc is still refused by the narrower mutant, so it is not a killer.
_Q2 = (
    "https://app.test/ok\u200b",
    "https://app.test/\u202eok",
    "https://app.test/\ue000",
    "https://app.test/\u0378ok",
)


def _boot(hosts: tuple[str, ...], *, redis: bool = False):
    app = FastAPI()
    cfg = ChannelConfig.development(
        secret=_SECRET,
        morph_html_policy="strict",
        navigate_allowed_hosts=hosts,
        observe="off",
        allow_memory_stores=True,
        require_cap=False,
        ws_require_origin=False,
        push_require_auth=False,
        mount_agent_mcp=True,
        agent_token="agent-tok",
    )
    ch = Channel.boot(app, config=cfg)
    holder: dict[str, dict] = {"op": {"op": "navigate", "href": "/"}}

    @ch.on("Go")
    def _go() -> Result:
        return Result.success(holder["op"])

    fake = None
    if redis:
        fake = fakeredis.FakeRedis(decode_responses=True)
        bus = RedisPushBus(fake)
        bus.morph_html_policy = "strict"
        bus._policy_bound = True
        bus.navigate_allowed_hosts = hosts
        ch.registry.push_bus = bus
        ch.push_bus = bus
    return app, ch, holder, fake


def _result_ops(blob: str) -> list[dict]:
    payloads: list[str] = []
    for line in blob.splitlines():
        if line.startswith("data: "):
            payloads.append(line[6:].strip())
    if not payloads:
        payloads.append(blob.strip())
    found: list[dict] = []

    def walk(node: object) -> None:
        if isinstance(node, dict):
            ops = node.get("ops")
            if isinstance(ops, list):
                found.extend(op for op in ops if isinstance(op, dict))
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for item in node:
                walk(item)

    for payload in payloads:
        if not payload or payload[0] not in "{[":
            continue
        try:
            walk(json.loads(payload))
        except json.JSONDecodeError:
            continue
    return found


def _delivered(blob: str) -> dict:
    ops = [op for op in _result_ops(blob) if op.get("op") in ("navigate", "noop")]
    assert ops, blob
    return ops[-1]


def _op(href: str, *, raw: bool) -> dict:
    if raw:
        return {"op": "navigate", "href": href}
    return navigate(href)


def _deliver(
    transport: str,
    href: str,
    *,
    hosts: tuple[str, ...] = (),
    request_host: str | None = None,
    raw: bool = False,
) -> dict:
    op = _op(href, raw=raw)
    if transport == "format_sse":
        body = Result.success(op).to_dict()
        blob = format_sse(
            body,
            policy="strict",
            allowed_hosts=hosts,
            origin_host=request_host,
        ).decode("utf-8")
        return _delivered(blob)
    if transport == "redis":
        app, ch, _holder, fake = _boot(hosts, redis=True)
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
        fake.publish(bus.backend._ch(_TOPIC), json.dumps(Result.success(op).to_dict()))
        deadline = time.time() + 2
        while time.time() < deadline and "data: " not in "".join(sink):
            time.sleep(0.02)
        thread.join(0.2)
        return _delivered("".join(sink))

    app, ch, holder, _fake = _boot(hosts)
    base = f"http://{request_host}" if request_host else "http://app.test"
    client = TestClient(app, base_url=base)
    if transport == "json":
        holder["op"] = op
        response = client.post(
            "/ux-channel/action",
            json={"v": "1", "action": "Go", "args": {}},
            headers={"Accept": "application/json"},
        )
        assert response.status_code == 200, response.text
        return _delivered(response.text)
    if transport == "sse":
        holder["op"] = op
        response = client.post(
            "/ux-channel/action",
            json={"v": "1", "action": "Go", "args": {}, "accept_stream": True},
            headers={"Accept": "text/event-stream"},
        )
        assert response.status_code == 200, response.text
        return _delivered(response.text)
    if transport == "push":
        return _published(client, ch, _TOPIC, op, mcp=False)
    if transport == "ws":
        with client.websocket_connect(f"/ux-channel/ws?topics={_TOPIC}") as ws:
            assert ws.receive_json()["type"] == "hello"
            assert ws.receive_json()["type"] == "subscribed"
            ch.live.publish(_TOPIC, result=Result.success(op))
            return _delivered(json.dumps(ws.receive_json()))
    if transport == "mcp":
        return _published(client, ch, _MCP_TOPIC, op, mcp=True)
    raise AssertionError(transport)


def _published(client: TestClient, ch: Channel, topic: str, op: dict, *, mcp: bool) -> dict:
    sink: list[str] = []
    ready = threading.Event()
    path = (
        "/ux-channel/mcp/resources/subscribe"
        if mcp
        else f"/ux-channel/push/{topic}"
    )
    headers = {"Authorization": "Bearer agent-tok"} if mcp else {}
    params = {"topic": topic} if mcp else None
    need = 2 if mcp else 1

    def _read() -> None:
        with client.stream("GET", path, params=params, headers=headers) as resp:
            assert resp.status_code == 200, resp.status_code
            ready.set()
            for chunk in resp.iter_text():
                sink.append(chunk)
                if "".join(sink).count("data: ") >= need:
                    return

    thread = threading.Thread(target=_read, daemon=True)
    thread.start()
    assert ready.wait(2), topic
    ch.live.publish(topic, result=Result.success(op))
    deadline = time.time() + 2
    while time.time() < deadline and "".join(sink).count("data: ") < need:
        time.sleep(0.01)
    thread.join(0.2)
    return _delivered("".join(sink))


@pytest.mark.parametrize("transport", _TRANSPORTS)
@pytest.mark.parametrize("href", _Q2)
def test_q2_format_and_private_chars_refuse_navigate(transport: str, href: str) -> None:
    """U+200B, U+202E, Co, and Cn in a same-origin navigate href are refused."""
    got = _deliver(transport, href, hosts=("app.test",), raw=True)
    assert got["op"] == "noop", (transport, href, got)


@pytest.mark.parametrize("transport", _NO_REQUEST)
@pytest.mark.parametrize("href", ("foo", "foo/bar", "./here", "?q=1", "#a"))
def test_q5_relative_without_origin_is_refused(transport: str, href: str) -> None:
    got = _deliver(transport, href)
    assert got["op"] == "noop", (transport, href, got)


@pytest.mark.parametrize("transport", _NO_REQUEST)
def test_q5_single_slash_without_origin_is_kept(transport: str) -> None:
    got = _deliver(transport, "/ok/more")
    assert got["op"] == "navigate", (transport, got)
    assert got["href"] == "/ok/more"


@pytest.mark.parametrize("transport", ("json", "sse"))
def test_q5_relative_with_a_request_host_is_kept(transport: str) -> None:
    got = _deliver(transport, "foo", request_host="app.test")
    assert got["op"] == "navigate", (transport, got)
    assert got["href"] == "foo"


@pytest.mark.parametrize("transport", _TRANSPORTS)
@pytest.mark.parametrize(
    "href",
    ("http:evil.test", "http:/evil.test", "https:evil.test/x", "https:///evil.test/"),
)
def test_q6_http_without_double_slash_is_refused(transport: str, href: str) -> None:
    got = _deliver(
        transport,
        href,
        hosts=("evil.test",),
        request_host="evil.test",
    )
    assert got["op"] == "noop", (transport, href, got)


@pytest.mark.parametrize("transport", _TRANSPORTS)
def test_q6_http_with_double_slash_is_kept(transport: str) -> None:
    href = "http://evil.test/x"
    got = _deliver(transport, href, hosts=("evil.test",), request_host="evil.test")
    assert got["op"] == "navigate", (transport, got)
    assert got["href"] == href


@pytest.mark.parametrize("transport", _TRANSPORTS)
@pytest.mark.parametrize("href", ("http://@evil.test", "https://@evil.test/", "http://@evil.test/a"))
def test_q7_empty_userinfo_is_refused(transport: str, href: str) -> None:
    got = _deliver(transport, href, hosts=("evil.test",), request_host="evil.test")
    assert got["op"] == "noop", (transport, href, got)


@pytest.mark.parametrize("transport", _TRANSPORTS)
def test_q7_userinfo_host_is_kept(transport: str) -> None:
    href = "http://user@evil.test/ok"
    got = _deliver(transport, href, hosts=("evil.test",), request_host="evil.test")
    assert got["op"] == "navigate", (transport, got)
    assert got["href"] == href


@pytest.mark.parametrize("transport", _TRANSPORTS)
@pytest.mark.parametrize("href", ("http://a@b@app.test", "http://a@b@app.test/ok"))
def test_q8_last_at_sign_is_the_host(transport: str, href: str) -> None:
    """The host is the label after the last ``@``. ``a@b@app.test`` stays."""
    got = _deliver(transport, href, hosts=("app.test",), request_host="app.test")
    assert got["op"] == "navigate", (transport, href, got)
    assert got["href"] == href


@pytest.mark.parametrize("transport", _TRANSPORTS)
def test_q8_first_label_is_not_the_host(transport: str) -> None:
    got = _deliver(
        transport,
        "http://app.test@evil.test/",
        hosts=("app.test",),
        request_host="app.test",
    )
    assert got["op"] == "noop", (transport, got)


@pytest.mark.parametrize("transport", _TRANSPORTS)
@pytest.mark.parametrize(
    "href",
    ("http://[2001:db8::1]/", "http://[2001:db8::1]:8443/ok"),
)
def test_q9_allowlisted_ipv6_is_kept(transport: str, href: str) -> None:
    got = _deliver(transport, href, hosts=("2001:db8::1",))
    assert got["op"] == "navigate", (transport, href, got)
    assert got["href"] == href


@pytest.mark.parametrize("transport", _TRANSPORTS)
def test_q9_other_ipv6_is_refused(transport: str) -> None:
    got = _deliver(
        transport,
        "http://[2001:db8::2]:8443/ok",
        hosts=("2001:db8::1",),
    )
    assert got["op"] == "noop", (transport, got)


@pytest.mark.parametrize("transport", _WITH_HOST)
def test_q9_ipv6_request_host_with_a_port_is_kept(transport: str) -> None:
    href = "http://[2001:db8::1]/ok"
    got = _deliver(transport, href, request_host="[2001:db8::1]:8443")
    assert got["op"] == "navigate", (transport, got)
    assert got["href"] == href


@pytest.mark.parametrize("transport", _WITH_HOST)
@pytest.mark.parametrize(
    "href",
    ("https://app.test/ok", "https://app.test:8443/ok", "http://app.test/a"),
)
def test_q14_request_host_port_still_matches(transport: str, href: str) -> None:
    """Host ``app.test:8000`` is the name ``app.test``. The navigate stays."""
    got = _deliver(transport, href, request_host="app.test:8000")
    assert got["op"] == "navigate", (transport, href, got)
    assert got["href"] == href


@pytest.mark.parametrize("transport", _WITH_HOST)
def test_q14_other_host_stays_refused(transport: str) -> None:
    got = _deliver(transport, "https://evil.test/ok", request_host="app.test:8000")
    assert got["op"] == "noop", (transport, got)
