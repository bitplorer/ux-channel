"""A channel with no policy is off on JSON, SSE, and push.

Strict is opt-in. A bare ``PushBus`` or a stream with no channel is the
only place a missing policy is strict. Policy off still refuses event
handlers, ``srcdoc``, and script URLs.
"""

from __future__ import annotations

import threading
import time

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from ux_channel import Channel, ChannelConfig, Result, create_channel, swap
from ux_channel.transport.push import PushBus
from ux_channel.transport.stream import resolve_stream_policy

_SECRET = "policy-off-secret-32chars-minimum!"
_TOPIC = "board"
_MARK = "PWN-OFF-9"
_CLICK = f'<div onclick="window.{_MARK}(1)">x</div>'

_REFUSALS: tuple[tuple[str, dict], ...] = (
    ("onclick", {"op": "set_attr", "target": "#a", "attrs": {"onclick": f"window.{_MARK}(1)"}}),
    ("srcdoc", {"op": "set_attr", "target": "#a", "attrs": {"srcdoc": f"<script>{_MARK}</script>"}}),
    ("javascript", {"op": "set_attr", "target": "#a", "attrs": {"href": f"javascript:{_MARK}(1)"}}),
    ("vbscript", {"op": "set_attr", "target": "#a", "attrs": {"href": f"vbscript:{_MARK}(1)"}}),
    (
        "data-html",
        {"op": "set_attr", "target": "#a", "attrs": {"src": f"data:text/html,{_MARK}"}},
    ),
    ("xlink", {"op": "set_attr", "target": "#a", "attrs": {"xlink:href": f"javascript:{_MARK}(1)"}}),
    ("action", {"op": "set_attr", "target": "#a", "attrs": {"action": f"javascript:{_MARK}(1)"}}),
    (
        "formaction",
        {"op": "set_attr", "target": "#a", "attrs": {"formaction": f"vbscript:{_MARK}(1)"}},
    ),
    ("control", {"op": "set_attr", "target": "#a", "attrs": {"href": "\x01//evil.example/x"}}),
    ("tab-slash", {"op": "set_attr", "target": "#a", "attrs": {"href": "/\t/evil.example/x"}}),
)


def _no_config() -> tuple[FastAPI, Channel]:
    app = FastAPI()
    reg, hub = create_channel(
        _SECRET,
        app=app,
        environment="development",
        require_cap=False,
    )
    return app, Channel(reg, hub=hub)


def _off_channel() -> tuple[FastAPI, Channel]:
    app = FastAPI()
    cfg = ChannelConfig.development(
        secret=_SECRET,
        morph_html_policy="off",
        observe="off",
        allow_memory_stores=True,
        require_cap=False,
        ws_require_origin=False,
        push_require_auth=False,
        mount_agent_mcp=True,
        agent_token="agent-tok",
    )
    return app, Channel.boot(app, config=cfg)


def _handler(ch: Channel, op: dict) -> None:
    @ch.on("Probe.go")
    def _go() -> Result:
        return Result.success(op)


def _kick(*buses: object) -> None:
    seen: set[int] = set()
    for bus in buses:
        if bus is None or id(bus) in seen:
            continue
        seen.add(id(bus))
        subs = getattr(getattr(bus, "backend", None), "_subs", None)
        if not subs:
            continue
        for queues in list(subs.values()):
            for q in list(queues):
                loop = getattr(q, "_loop", None)
                if loop is not None and not loop.is_closed():
                    loop.call_soon_threadsafe(lambda: None)


def _read_push(client: TestClient, ch: Channel, op: dict) -> str:
    sink: list[str] = []
    ready = threading.Event()

    def _run() -> None:
        with client.stream("GET", f"/ux-channel/push/{_TOPIC}") as resp:
            assert resp.status_code == 200, resp.status_code
            ready.set()
            for chunk in resp.iter_text():
                sink.append(chunk)
                if _MARK in "".join(sink) or "evil.example" in "".join(sink):
                    return

    thread = threading.Thread(target=_run, daemon=True)
    thread.start()
    assert ready.wait(2)
    ch.live.publish(_TOPIC, result=Result.success(op))
    _kick(ch.registry.push_bus)
    deadline = time.time() + 1.0
    while time.time() < deadline and not sink:
        time.sleep(0.02)
    thread.join(0.1)
    return "".join(sink)


def test_unknown_policy_strings_raise_and_bare_bus_is_strict() -> None:
    for bad in ("strict ", " strict", "strcit", "on", "Strict"):
        with pytest.raises(ValueError):
            ChannelConfig.development(
                secret=_SECRET,
                morph_html_policy=bad,
                observe="off",
                allow_memory_stores=True,
            )
        bus = PushBus()
        bus.morph_html_policy = bad
        with pytest.raises(ValueError):
            bus.outbound_policy()
        with pytest.raises(ValueError):
            resolve_stream_policy(bad)
    blank = ChannelConfig.development(
        secret=_SECRET,
        morph_html_policy="",
        observe="off",
        allow_memory_stores=True,
    )
    assert blank.morph_html_policy == "off"
    assert PushBus().outbound_policy() == "strict"
    assert resolve_stream_policy(None) == "strict"


def test_no_config_is_off_for_json_sse_and_push() -> None:
    """No config matches explicit off: markup stays, on every response shape."""
    app, ch = _no_config()
    _handler(ch, swap("#t", _CLICK))
    client = TestClient(app)
    body = {"v": "1", "action": "Probe.go", "args": {}}
    # No config still requires the CSRF header. That is not the policy.
    headers = {"X-Channel": "1"}
    json_res = client.post("/ux-channel/action", json=body, headers=headers)
    sse_res = client.post(
        "/ux-channel/action",
        json=body,
        headers={**headers, "Accept": "text/event-stream"},
    )
    pushed = _read_push(client, ch, swap("#t", _CLICK))
    assert json_res.status_code == 200, json_res.text
    for label, blob in (
        ("json", json_res.text),
        ("sse", sse_res.text),
        ("push", pushed),
    ):
        assert "onclick" in blob.lower(), label + " " + blob
        assert _MARK in blob, label + " " + blob


def test_explicit_off_matches_strict_across_json_and_sse() -> None:
    app, ch = _off_channel()
    _handler(ch, swap("#t", _CLICK))
    client = TestClient(app)
    body = {"v": "1", "action": "Probe.go", "args": {}}
    json_blob = client.post("/ux-channel/action", json=body).text
    sse_blob = client.post(
        "/ux-channel/action",
        json=body,
        headers={"Accept": "text/event-stream"},
    ).text
    assert ("onclick" in json_blob.lower()) == ("onclick" in sse_blob.lower())
    assert "onclick" in json_blob.lower(), json_blob

    app_s = FastAPI()
    cfg = ChannelConfig.development(
        secret=_SECRET,
        morph_html_policy="strict",
        observe="off",
        allow_memory_stores=True,
        require_cap=False,
    )
    ch_s = Channel.boot(app_s, config=cfg)
    _handler(ch_s, swap("#t", _CLICK))
    client_s = TestClient(app_s)
    json_s = client_s.post("/ux-channel/action", json=body).text
    sse_s = client_s.post(
        "/ux-channel/action",
        json=body,
        headers={"Accept": "text/event-stream"},
    ).text
    assert "onclick" not in json_s.lower(), json_s
    assert "onclick" not in sse_s.lower(), sse_s


def _refuse_blob(blob: str, name: str) -> None:
    assert _MARK not in blob, name + " " + blob
    assert "javascript:" not in blob.lower(), name
    assert "vbscript:" not in blob.lower(), name
    assert "data:text/html" not in blob.lower(), name
    assert "evil.example" not in blob, name


def test_off_json_refuses_handlers_and_script_urls() -> None:
    app, ch = _off_channel()

    @ch.on("Probe.go")
    def _go(which: str = "onclick") -> Result:
        op = dict(_REFUSALS[0][1])
        for name, candidate in _REFUSALS:
            if name == which:
                op = candidate
                break
        return Result.success(op)

    client = TestClient(app)
    for name, _op in _REFUSALS:
        res = client.post(
            "/ux-channel/action",
            json={"v": "1", "action": "Probe.go", "args": {"which": name}},
        )
        assert res.status_code == 200, res.text
        _refuse_blob(res.text, name)


def test_off_sse_refuses_handlers_and_script_urls() -> None:
    app, ch = _off_channel()

    @ch.on("Probe.go")
    def _go(which: str = "onclick") -> Result:
        for name, candidate in _REFUSALS:
            if name == which:
                return Result.success(candidate)
        raise AssertionError(which)

    client = TestClient(app)
    for name, _op in _REFUSALS:
        res = client.post(
            "/ux-channel/action",
            json={"v": "1", "action": "Probe.go", "args": {"which": name}},
            headers={"Accept": "text/event-stream"},
        )
        _refuse_blob(res.text, name)


def test_off_push_refuses_handlers_and_script_urls() -> None:
    app, ch = _off_channel()
    client = TestClient(app)
    for name, op in _REFUSALS:
        blob = _read_push(client, ch, op)
        _refuse_blob(blob, name)


def test_off_ws_refuses_handlers_and_script_urls() -> None:
    app, ch = _off_channel()
    client = TestClient(app)
    with client.websocket_connect(f"/ux-channel/ws?topics={_TOPIC}") as ws:
        assert ws.receive_json()["type"] == "hello"
        assert ws.receive_json()["type"] == "subscribed"
        for name, op in _REFUSALS:
            ch.live.publish(_TOPIC, result=Result.success(op))
            _kick(ch.registry.push_bus)
            msg = ws.receive_json()
            _refuse_blob(str(msg), name)


def test_off_mcp_refuses_handlers_and_script_urls() -> None:
    app, ch = _off_channel()
    client = TestClient(app)
    topic = "mcp.resource.board"
    headers = {"Authorization": "Bearer agent-tok"}
    sink: list[str] = []
    ready = threading.Event()

    def _run() -> None:
        with client.stream(
            "GET",
            "/ux-channel/mcp/resources/subscribe",
            params={"topic": topic},
            headers=headers,
        ) as resp:
            assert resp.status_code == 200, resp.text
            ready.set()
            for chunk in resp.iter_text():
                sink.append(chunk)

    thread = threading.Thread(target=_run, daemon=True)
    thread.start()
    assert ready.wait(2)
    for name, op in _REFUSALS:
        before = len(sink)
        ch.live.publish(topic, result=Result.success(op))
        _kick(ch.registry.push_bus)
        deadline = time.time() + 1.0
        while time.time() < deadline and len(sink) == before:
            time.sleep(0.02)
        _refuse_blob("".join(sink[before:]), name)
    thread.join(0.1)
