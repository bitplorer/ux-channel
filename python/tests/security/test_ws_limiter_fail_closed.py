"""A WebSocket rate limiter that raises refuses the socket; it never allows."""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from ux_channel import ChannelConfig
from ux_channel.asgi.fastapi import mount_channel
from ux_channel.host.registry import ActionRegistry
from ux_channel.transport.ws_limits import get_ws_limiter, set_ws_limiter

SECRET = "dev-secret-key-32chars-minimum!!!!"


class _LimiterDown(ConnectionError):
    pass


class _BrokenLimiter:
    def __init__(self, *, connect: bool, message: bool) -> None:
        self.connect, self.message = connect, message

    def allow_connect(self, key):
        if self.connect:
            raise _LimiterDown("limiter store unreachable")
        return True, "ok"

    def allow_message(self, key):
        if self.message:
            raise _LimiterDown("limiter store unreachable")
        return True, "ok"


@pytest.fixture
def client():
    cfg = ChannelConfig.development(
        secret=SECRET, enforce_same_origin=False, rate_limit_per_minute=0
    )
    app = FastAPI()
    mount_channel(app, ActionRegistry.from_config(cfg), config=cfg)
    prev = get_ws_limiter()
    yield TestClient(app)
    set_ws_limiter(prev)


def test_connect_limiter_error_refuses_socket(client):
    set_ws_limiter(_BrokenLimiter(connect=True, message=False))
    with pytest.raises(_LimiterDown):
        with client.websocket_connect("/ux-channel/ws") as ws:
            ws.receive_json()


def test_message_limiter_error_ends_socket(client):
    set_ws_limiter(_BrokenLimiter(connect=False, message=True))
    with pytest.raises(_LimiterDown):
        with client.websocket_connect("/ux-channel/ws") as ws:
            assert ws.receive_json()["type"] == "hello"
            ws.send_json({"type": "ping"})
            ws.receive_json()
