"""A raw push that arrives on Redis is filtered like a local publish.

``PushBus.publish`` filters before it writes. Another worker can publish
the same topic straight to Redis. That copy must not reach ``/push`` with
a live ``onclick`` when this channel's policy would have removed it.
"""

from __future__ import annotations

import json
import threading
import time

import fakeredis
from fastapi import FastAPI
from fastapi.testclient import TestClient

from ux_channel import Channel, ChannelConfig
from ux_channel.redis_extra import RedisPushBus

_SECRET = "redis-inbound-secret-32chars-min!"
_TOPIC = "board"
_MARK = "REDIS-MARK-9f3c"
_HTML = f'<div id="m">{_MARK}</div><div onclick="window.PWN(1)">x</div>'


def _boot(policy: str):
    app = FastAPI()
    cfg = ChannelConfig.development(
        secret=_SECRET,
        morph_html_policy=policy,
        observe="off",
        allow_memory_stores=True,
    )
    ch = Channel.boot(app, config=cfg)
    fake = fakeredis.FakeRedis(decode_responses=True)
    bus = RedisPushBus(fake)
    bus.morph_html_policy = policy
    bus._policy_bound = True
    bus.navigate_allowed_hosts = ()
    ch.registry.push_bus = bus
    ch.push_bus = bus
    return app, bus, fake


def _kick(bus: object) -> None:
    local = getattr(getattr(bus, "backend", None), "_local", None) or {}
    for queues in list(local.values()):
        for q in list(queues):
            loop = getattr(q, "_loop", None)
            if loop is not None and not loop.is_closed():
                loop.call_soon_threadsafe(lambda: None)


def _sse(client: TestClient, sink: list[str], ready: threading.Event) -> None:
    with client.stream("GET", f"/ux-channel/push/{_TOPIC}") as resp:
        assert resp.status_code == 200, resp.status_code
        ready.set()
        for chunk in resp.iter_text():
            sink.append(chunk)
            if _MARK in "".join(sink):
                return


def test_redis_inbound_onclick_is_filtered_on_push() -> None:
    """Publish the raw onclick on Redis, not through ``PushBus.publish``."""
    app, bus, fake = _boot("strict")
    client = TestClient(app)
    sink: list[str] = []
    ready = threading.Event()
    thread = threading.Thread(target=_sse, args=(client, sink, ready), daemon=True)
    thread.start()
    assert ready.wait(2), "SSE route did not open"
    deadline = time.time() + 1.5
    while time.time() < deadline and _TOPIC not in bus.backend._redis_topics:
        time.sleep(0.01)
    assert _TOPIC in bus.backend._redis_topics

    raw = {
        "ok": True,
        "ops": [{"op": "swap", "target": "#t", "html": _HTML}],
    }
    fake.publish(bus.backend._ch(_TOPIC), json.dumps(raw))

    deadline = time.time() + 2.0
    while time.time() < deadline and _MARK not in "".join(sink):
        _kick(bus)
        time.sleep(0.05)
    body = "".join(sink)
    assert _MARK in body, body
    assert "onclick" not in body.lower(), body
    thread.join(timeout=1)
