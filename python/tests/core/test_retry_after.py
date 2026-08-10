
"""Retry-After parse, override, batch, HTTP headers."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from ux_channel import Channel, ChannelConfig
from ux_channel.backoff import (
    apply_retry_after_override,
    delay_with_retry_after,
    extract_retry_after_s,
    parse_retry_after,
    BackoffPolicy,
)
from ux_channel.batch import dispatch_batch
from ux_channel.error_map import ensure_error_meta
from ux_channel.types import Result


def test_parse_retry_after_seconds():
    assert parse_retry_after("12") == 12.0
    assert parse_retry_after(3.5) == 3.5
    assert parse_retry_after(None) is None


def test_extract_from_meta_and_default():
    r = Result.failure("rate_limited", "x", retry_after=9)
    assert extract_retry_after_s(r) == 9.0
    # ensure_error_meta does not invent retry_after
    r2 = ensure_error_meta(Result.failure("rate_limited", "x"))
    assert extract_retry_after_s(r2) is None


def test_apply_modes():
    assert apply_retry_after_override(50, 2.0, mode="max") == (2000.0, True)
    assert apply_retry_after_override(5000, 1.0, mode="max") == (5000.0, True)
    assert apply_retry_after_override(50, 2.0, mode="replace") == (2000.0, True)
    assert apply_retry_after_override(50, None, mode="max") == (50.0, False)


def test_delay_with_retry_after_overrides_fixed():
    r = Result.failure("rate_limited", "x", retryable=True, retry_after=3)
    policy = BackoffPolicy(strategy="fixed", base_ms=50, max_ms=60_000)
    d = delay_with_retry_after(1, r, policy=policy, retry_after_mode="max")
    assert d["override"] is True
    assert d["wait_ms"] == 3000.0
    assert d["computed_ms"] == 50.0


def test_batch_uses_retry_after():
    ch = Channel.boot(
        FastAPI(),
        config=ChannelConfig.development(secret="dev-secret-key-32chars-minimum!!!!"),
    )
    hits = {"n": 0}

    @ch.on(name="T.ra", idempotent=True)
    def ra():
        hits["n"] += 1
        if hits["n"] < 2:
            return Result.failure("rate_limited", "wait", retryable=True, retry_after=0.01)
        return ch.done()

    out = dispatch_batch(
        ch.registry,
        [{"v": "1", "action": "T.ra", "args": {}, "cap": ch.registry.mint("T.ra", {})}],
        retry_retryable=True,
        max_retries=1,
        retry_backoff_ms=1,
        retry_backoff_strategy="fixed",
    )
    assert out["ok"]
    det = out["meta"]["retry"]["delay_details"][0][0]
    assert det["override"] is True
    assert det["retry_after_s"] == 0.01
    assert det["wait_ms"] == 10.0


def test_http_retry_after_header():
    app = FastAPI()
    ch = Channel.boot(
        app,
        config=ChannelConfig.development(secret="dev-secret-key-32chars-minimum!!!!"),
    )

    @ch.on(name="T.hdr", idempotent=True)
    def hdr():
        return Result.failure("rate_limited", "no", retryable=True, retry_after=42)

    client = TestClient(app)
    res = client.post(
        "/ux-channel/action",
        json={
            "v": "1",
            "action": "T.hdr",
            "args": {},
            "cap": ch.registry.mint("T.hdr", {}),
        },
        headers={"X-Channel": "1", "Content-Type": "application/json"},
    )
    assert res.status_code == 429
    assert res.headers["Retry-After"] == "42"
    assert res.json()["meta"]["retry_after"] == 42


def test_client_js_has_retry_after_helpers():
    from pathlib import Path
    js = Path("src/ux_channel/static/ux-channel.js").read_text()
    assert "parseRetryAfter" in js
    assert "mergeRetryAfter" in js
    assert "channel:retryAfter" in js
