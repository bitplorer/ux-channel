"""Two channels in one process keep their push routes apart.

A's ``/push`` SSE, ``/ws``, and MCP subscribe must read A's bus. Today
``fastapi.py`` subscribes with ``get_push_bus()``, so after B boots the
global bus is B's: A's subscribers receive B's unfiltered ``onclick`` and
miss A's own publish.
"""

from __future__ import annotations

import gc
import json
import threading
import time

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from ux_channel import Channel, ChannelConfig, Result, swap
from ux_channel.transport import push as push_mod
from ux_channel.transport.push import PushBus, get_push_bus, set_push_bus

_SECRET = "route-bus-secret-32chars-minimum!"
_TOPIC = "board"
_B_MARK = "B-MARK-9f3c"
_B_CLICK = f'<div onclick="window.PWN(1)">{_B_MARK}</div>'
_B_ERROR = '<img src="x" onerror="window.PWN(2)">'
_A_MARK = "A-MARK-9f3c"


def _reset_push() -> None:
    push_mod._bus = None
    push_mod._owners.clear()
    gc.collect()


def _kick(*buses: object) -> None:
    """Wake a TestClient stream blocked in ``asyncio.Queue.get``.

    ``PushBus.publish`` uses ``put_nowait`` from the test thread. That schedules
    the waiter without waking the loop the stream is blocked on, so a body that
    is already queued never shows up. This only unblocks the read.
    """
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


def _boot(policy: str | None = "off", hosts: tuple[str, ...] = ()):
    app = FastAPI()
    kwargs: dict[str, object] = {
        "secret": _SECRET,
        "observe": "off",
        "allow_memory_stores": True,
        "mount_agent_mcp": True,
        "agent_token": "agent-tok",
        "ws_require_origin": False,
        "navigate_allowed_hosts": hosts,
    }
    if policy is not None:
        kwargs["morph_html_policy"] = policy
    cfg = ChannelConfig.development(**kwargs)  # type: ignore[arg-type]
    ch = Channel.boot(app, config=cfg)
    return app, ch


def _sse(client: TestClient, topic: str, sink: list[str], ready: threading.Event) -> None:
    with client.stream("GET", f"/ux-channel/push/{topic}") as resp:
        assert resp.status_code == 200, resp.status_code
        ready.set()
        for chunk in resp.iter_text():
            sink.append(chunk)
            if len(sink) >= 4:
                return


def _start_sse(client: TestClient, topic: str) -> tuple[list[str], threading.Thread, threading.Event]:
    sink: list[str] = []
    ready = threading.Event()
    thread = threading.Thread(target=_sse, args=(client, topic, sink, ready), daemon=True)
    thread.start()
    assert ready.wait(2), "SSE route did not open"
    return sink, thread, ready


def _blob(chunks: list[str]) -> str:
    return "".join(chunks)


def _wait_blob(chunks: list[str], needle: str, timeout: float = 1.5) -> str:
    deadline = time.time() + timeout
    while time.time() < deadline and needle not in _blob(chunks):
        time.sleep(0.05)
    return _blob(chunks)


@pytest.fixture(autouse=True)
def _isolate_buses():
    _reset_push()
    yield
    _reset_push()


def test_push_sse_a_does_not_receive_b_and_does_receive_itself() -> None:
    """Reproduce the blocked route: A is subscribed, B publishes onclick, A publishes.

    One stream at a time. Two ``TestClient`` streams in one process drop A's
    body on the floor, which hides the crosstalk this test has to show.
    """
    app_a, ch_a = _boot("strict", ("app.test",))
    _app_b, ch_b = _boot("off")
    client_a = TestClient(app_a)
    sink_a, thread_a, _ = _start_sse(client_a, _TOPIC)

    ch_b.live.publish(_TOPIC, result=Result.success(swap("#t", _B_CLICK)))
    ch_a.live.publish(_TOPIC, result=Result.success(swap("#t", f"<b>{_A_MARK}</b>")))
    _kick(ch_a.registry.push_bus, ch_b.registry.push_bus)
    got_a = _wait_blob(sink_a, _A_MARK)
    thread_a.join(0.1)
    assert "onclick" not in got_a.lower(), got_a
    assert _A_MARK in got_a, got_a
    assert _B_MARK not in got_a, got_a

    client_b = TestClient(_app_b)
    sink_b, thread_b, _ = _start_sse(client_b, _TOPIC)
    ch_b.live.publish(_TOPIC, result=Result.success(swap("#t", _B_CLICK)))
    ch_a.live.publish(_TOPIC, result=Result.success(swap("#t", f"<b>{_A_MARK}</b>")))
    _kick(ch_a.registry.push_bus, ch_b.registry.push_bus)
    got_b = _wait_blob(sink_b, _B_MARK)
    thread_b.join(0.1)
    assert _B_MARK in got_b, got_b
    assert "onclick" not in got_b.lower(), got_b
    assert _A_MARK not in got_b, got_b


def test_strict_push_sse_never_receives_b_onerror_or_evil_navigate() -> None:
    app_a, ch_a = _boot("strict", ("app.test",))
    app_b, ch_b = _boot("off")
    client_a = TestClient(app_a)
    sink_a, thread_a, _ = _start_sse(client_a, _TOPIC)
    ch_b.live.publish(_TOPIC, result=Result.success(swap("#t", _B_ERROR)))
    ch_b.live.publish(
        _TOPIC, result=Result.success({"op": "navigate", "href": "https://evil.test/x"})
    )
    ch_a.live.publish(
        _TOPIC, result=Result.success({"op": "navigate", "href": "https://app.test/ok"})
    )
    _kick(ch_a.registry.push_bus, ch_b.registry.push_bus)
    got = _wait_blob(sink_a, "onerror")
    thread_a.join(0.1)
    assert "onerror" not in got.lower(), got
    assert "evil.test" not in got, got
    assert "app.test" in got, got


def test_ws_a_does_not_receive_b_and_does_receive_itself() -> None:
    app_a, ch_a = _boot("strict", ("app.test",))
    app_b, ch_b = _boot("off")
    client_a = TestClient(app_a)
    client_b = TestClient(app_b)
    with client_a.websocket_connect(f"/ux-channel/ws?topics={_TOPIC}") as ws_a:
        with client_b.websocket_connect(f"/ux-channel/ws?topics={_TOPIC}") as ws_b:
            assert ws_a.receive_json()["type"] == "hello"
            assert ws_a.receive_json()["type"] == "subscribed"
            assert ws_b.receive_json()["type"] == "hello"
            assert ws_b.receive_json()["type"] == "subscribed"
            ch_b.live.publish(_TOPIC, result=Result.success(swap("#t", _B_CLICK)))
            ch_a.live.publish(_TOPIC, result=Result.success(swap("#t", f"<b>{_A_MARK}</b>")))
            _kick(ch_a.registry.push_bus, ch_b.registry.push_bus)
            got_a = _collect_ws(ws_a)
            got_b = _collect_ws(ws_b)
    assert "onclick" not in got_a.lower(), got_a
    assert _A_MARK in got_a, got_a
    assert _B_MARK not in got_a, got_a
    assert _B_MARK in got_b, got_b
    assert "onclick" not in got_b.lower(), got_b
    assert _A_MARK not in got_b, got_b


def test_mcp_a_does_not_receive_b_and_does_receive_itself() -> None:
    """Same crosstalk as ``/push``, one MCP stream at a time."""
    app_a, ch_a = _boot("strict", ("app.test",))
    app_b, ch_b = _boot("off")
    headers = {"Authorization": "Bearer agent-tok"}
    topic = "mcp.resource.board"
    client_a = TestClient(app_a)
    sink_a, thread_a, _ = _start_mcp(client_a, topic, headers)
    ch_b.live.publish(topic, result=Result.success(swap("#t", _B_CLICK)))
    ch_a.live.publish(topic, result=Result.success(swap("#t", f"<b>{_A_MARK}</b>")))
    _kick(ch_a.registry.push_bus, ch_b.registry.push_bus)
    got_a = _wait_blob(sink_a, _A_MARK)
    thread_a.join(0.1)
    assert "onclick" not in got_a.lower(), got_a
    assert _A_MARK in got_a, got_a
    assert _B_MARK not in got_a, got_a

    client_b = TestClient(app_b)
    sink_b, thread_b, _ = _start_mcp(client_b, topic, headers)
    ch_b.live.publish(topic, result=Result.success(swap("#t", _B_CLICK)))
    ch_a.live.publish(topic, result=Result.success(swap("#t", f"<b>{_A_MARK}</b>")))
    _kick(ch_a.registry.push_bus, ch_b.registry.push_bus)
    got_b = _wait_blob(sink_b, _B_MARK)
    thread_b.join(0.1)
    assert _B_MARK in got_b, got_b
    assert "onclick" not in got_b.lower(), got_b
    assert _A_MARK not in got_b, got_b


def test_get_push_bus_raises_when_two_channels_are_booted() -> None:
    _app_a, ch_a = _boot("strict", ("app.test",))
    _app_b, ch_b = _boot("off")
    with pytest.raises(RuntimeError, match="channel"):
        get_push_bus()
    assert get_push_bus(ch_a) is ch_a.registry.push_bus
    assert get_push_bus(ch_b) is ch_b.registry.push_bus
    assert get_push_bus(ch_a) is not get_push_bus(ch_b)


def test_set_push_bus_repoints_the_open_route() -> None:
    """``/push`` reads the registry bus, so ``set_push_bus`` must move it."""
    app, ch = _boot("off")
    replacement = PushBus()
    set_push_bus(replacement)
    client = TestClient(app)
    sink, thread, _ = _start_sse(client, _TOPIC)
    body = Result.success(swap("#t", f"<b>{_A_MARK}</b>")).to_dict()
    replacement.publish(_TOPIC, body)
    _kick(ch.registry.push_bus, replacement)
    got = _wait_blob(sink, _A_MARK)
    thread.join(0.1)
    assert ch.registry.push_bus is replacement
    assert _A_MARK in got, got


def test_one_channel_get_push_bus_matches_main() -> None:
    _app, ch = _boot("off")
    assert get_push_bus() is ch.registry.push_bus
    assert get_push_bus(ch) is ch.registry.push_bus


def _collect_ws(ws, limit: int = 6) -> str:
    messages: list[str] = []

    def _read() -> None:
        for _ in range(limit):
            try:
                messages.append(json.dumps(ws.receive_json()))
            except Exception:
                return

    thread = threading.Thread(target=_read, daemon=True)
    thread.start()
    thread.join(0.6)
    return "".join(messages)


def _start_mcp(client: TestClient, topic: str, headers: dict[str, str]):
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
                if len(sink) >= 4:
                    return

    thread = threading.Thread(target=_run, daemon=True)
    thread.start()
    assert ready.wait(2), "MCP subscribe did not open"
    return sink, thread, ready
