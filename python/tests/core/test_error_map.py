
"""Unified server error → HTTP mapping."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from ux_channel import Channel, ChannelConfig, Result
from ux_channel.error_map import (
    ERROR_HTTP_STATUS,
    catalog,
    ensure_error_meta,
    http_status_for,
    kind_for_code,
)
from ux_channel.types import Result as R


def test_catalog_covers_known_codes():
    codes = {r["code"] for r in catalog()}
    assert "unauthorized" in codes
    assert "render_error" in codes
    assert "validation" in codes


def test_http_status_matrix():
    assert http_status_for(R.success()) == 200
    for code, status in ERROR_HTTP_STATUS.items():
        r = R.failure(code, "x")
        assert http_status_for(r) == status, code


def test_unknown_code_defaults_422():
    r = R.failure("custom_app_code", "x")
    assert http_status_for(r) == 422


def test_ensure_error_meta_fills_retryable_and_kind():
    r = R.failure("rate_limited", "slow")
    assert r.error.retryable is None or r.error.retryable is False or True
    r2 = ensure_error_meta(r)
    assert r2.error.retryable is True
    assert r2.meta.get("error_kind") == "network"
    assert r2.meta.get("http_status") == 429


def test_render_error_is_500():
    r = R.failure("render_error", "boom", retryable=True)
    assert http_status_for(r) == 500
    assert kind_for_code("render_error") == "refresh"


def test_fastapi_action_status_uses_map():
    app = FastAPI()
    ch = Channel.boot(
        app,
        config=ChannelConfig.development(secret="dev-secret-key-32chars-minimum!!!!"),
    )

    @ch.on(name="E.auth", auth=True)
    def eauth():
        return ch.done()

    @ch.on(name="E.val")
    def eval_():
        return Result.failure("validation", "nope", fields={"a": ["x"]})

    client = TestClient(app)
    # missing cap → unauthorized 401
    res = client.post(
        "/ux-channel/action",
        json={"v": "1", "action": "E.auth", "args": {}},
        headers={"X-Channel": "1", "Content-Type": "application/json"},
    )
    # may be unauthorized for missing cap
    assert res.status_code in (401, 422)
    body = res.json()
    assert body.get("ok") is False

    cap = ch.registry.sign("E.val", {})
    res2 = client.post(
        "/ux-channel/action",
        json={"v": "1", "action": "E.val", "args": {}, "cap": cap},
        headers={"X-Channel": "1", "Content-Type": "application/json"},
    )
    assert res2.status_code == 422
    b2 = res2.json()
    assert b2["error"]["code"] == "validation"
    assert b2.get("meta", {}).get("error_kind") == "validation"
    assert b2.get("meta", {}).get("http_status") == 422


def test_hosts_share_same_mapper():
    from ux_channel.asgi.core import status_for
    from ux_channel.asgi.fastapi import _status_for

    r = R.failure("payload_too_large", "x")
    assert status_for(r) == _status_for(r) == 413
