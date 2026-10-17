"""Starlette /action enforces allowed_origins and enforce_same_origin (fail closed).

The check lives in ``asgi.pipeline.preflight_action``; this locks the Starlette
adapter to it.
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest

pytest.importorskip("starlette")
from starlette.applications import Starlette  # noqa: E402
from starlette.testclient import TestClient  # noqa: E402

from ux_channel.asgi.starlette import mount_channel_starlette  # noqa: E402
from ux_channel.host.registry import ActionRegistry  # noqa: E402

HDRS = {"content-type": "application/json", "x-channel": "1"}


def _post(config, origin):
    app = Starlette()
    mount_channel_starlette(app, ActionRegistry("s" * 40), config=config)
    r = TestClient(app).post("/ux-channel/action", content=b'{"action":"x"}', headers={**HDRS, "origin": origin})
    return r.status_code, r.json()["error"]["message"]


ALLOW = SimpleNamespace(allowed_origins=("https://good.example",), enforce_same_origin=True)
SAME = SimpleNamespace(allowed_origins=(), enforce_same_origin=True)


@pytest.mark.parametrize("config", [ALLOW, SAME, None])
@pytest.mark.parametrize("origin", ["https://evil.example", "null"])
def test_foreign_origin_denied(config, origin):
    assert _post(config, origin) == (403, "origin not allowed")


def test_allowed_origin_passes_preflight():
    assert _post(ALLOW, "https://good.example")[0] == 404  # reached dispatch


def test_allow_list_is_exact_even_for_same_host():
    assert _post(ALLOW, "http://testserver") == (403, "origin not allowed")


@pytest.mark.parametrize("config", [SAME, None])
def test_same_origin_passes_preflight(config):
    assert _post(config, "http://testserver")[0] == 404
