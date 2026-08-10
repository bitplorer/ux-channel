
"""Batch per-item retry for retryable failures."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from ux_channel import Channel, ChannelConfig
from ux_channel.batch import dispatch_batch, item_is_retryable
from ux_channel.types import Result


def test_item_is_retryable_matrix():
    assert item_is_retryable(Result.success()) is False
    assert item_is_retryable(Result.failure("validation", "x")) is False
    assert item_is_retryable(Result.failure("unauthorized", "x")) is False
    r = Result.failure("rate_limited", "slow")
    # ensure_error_meta not required — should_retry via code when retryable is None
    r.error.retryable = None
    assert item_is_retryable(r) is True
    r2 = Result.failure("rate_limited", "slow", retryable=False)
    assert item_is_retryable(r2) is False
    r3 = Result.failure("validation", "x", retryable=True)
    assert item_is_retryable(r3) is True  # explicit wins


def test_retry_recovers_flaky_action():
    ch = Channel.boot(
        FastAPI(),
        config=ChannelConfig.development(secret="dev-secret-key-32chars-minimum!!!!"),
    )
    hits = {"n": 0}

    @ch.on(name="R.flaky", idempotent=True)
    def flaky():
        hits["n"] += 1
        if hits["n"] < 2:
            return Result.failure("rate_limited", "wait", retryable=True)
        return ch.done(notice="ok")

    cap = ch.registry.mint("R.flaky", {})
    out = dispatch_batch(
        ch.registry,
        [{"v": "1", "action": "R.flaky", "args": {}, "cap": cap}],
        retry_retryable=True,
        max_retries=2,
        retry_backoff_ms=0,
    )
    assert out["ok"] is True
    assert out["meta"]["retry"]["enabled"] is True
    assert out["meta"]["retry"]["recovered"] == 1
    assert out["meta"]["retry"]["attempts"] == [2]
    assert out["meta"]["retry"]["retried_indices"] == [0]
    assert hits["n"] == 2


def test_retry_disabled_by_default():
    ch = Channel.boot(
        FastAPI(),
        config=ChannelConfig.development(secret="dev-secret-key-32chars-minimum!!!!"),
    )
    hits = {"n": 0}

    @ch.on(name="R.once", idempotent=True)
    def once():
        hits["n"] += 1
        return Result.failure("rate_limited", "wait", retryable=True)

    cap = ch.registry.mint("R.once", {})
    out = dispatch_batch(
        ch.registry,
        [{"v": "1", "action": "R.once", "args": {}, "cap": cap}],
    )
    assert out["ok"] is False
    assert hits["n"] == 1
    assert out["meta"]["retry"]["enabled"] is False
    assert out["meta"]["retry"]["attempts"] == [1]


def test_non_retryable_not_retried():
    ch = Channel.boot(
        FastAPI(),
        config=ChannelConfig.development(secret="dev-secret-key-32chars-minimum!!!!"),
    )
    hits = {"n": 0}

    @ch.on(name="R.val", idempotent=True)
    def val():
        hits["n"] += 1
        return Result.failure("validation", "nope")

    cap = ch.registry.mint("R.val", {})
    out = dispatch_batch(
        ch.registry,
        [{"v": "1", "action": "R.val", "args": {}, "cap": cap}],
        retry_retryable=True,
        max_retries=3,
        retry_backoff_ms=0,
    )
    assert hits["n"] == 1
    assert out["meta"]["retry"]["retried_indices"] == []
    assert out["meta"]["retry"]["recovered"] == 0


def test_retry_exhausted():
    ch = Channel.boot(
        FastAPI(),
        config=ChannelConfig.development(secret="dev-secret-key-32chars-minimum!!!!"),
    )
    hits = {"n": 0}

    @ch.on(name="R.always", idempotent=True)
    def always():
        hits["n"] += 1
        return Result.failure("timeout", "nope", retryable=True)

    cap = ch.registry.mint("R.always", {})
    out = dispatch_batch(
        ch.registry,
        [{"v": "1", "action": "R.always", "args": {}, "cap": cap}],
        retry_retryable=True,
        max_retries=2,
        retry_backoff_ms=0,
    )
    assert out["ok"] is False
    assert hits["n"] == 3  # 1 + 2 retries
    assert out["meta"]["retry"]["exhausted"] == 1
    assert out["meta"]["retry"]["attempts"] == [3]


def test_mixed_batch_retry_only_retryable():
    ch = Channel.boot(
        FastAPI(),
        config=ChannelConfig.development(secret="dev-secret-key-32chars-minimum!!!!"),
    )
    hits = {"flaky": 0, "val": 0}

    @ch.on(name="R.flaky2", idempotent=True)
    def flaky2():
        hits["flaky"] += 1
        if hits["flaky"] < 2:
            return Result.failure("unavailable", "x", retryable=True)
        return ch.done()

    @ch.on(name="R.val2", idempotent=True)
    def val2():
        hits["val"] += 1
        return Result.failure("validation", "no")

    out = dispatch_batch(
        ch.registry,
        [
            {
                "v": "1",
                "action": "R.flaky2",
                "args": {},
                "cap": ch.registry.mint("R.flaky2", {}),
            },
            {
                "v": "1",
                "action": "R.val2",
                "args": {},
                "cap": ch.registry.mint("R.val2", {}),
            },
        ],
        retry_retryable=True,
        max_retries=1,
        retry_backoff_ms=0,
    )
    assert hits["flaky"] == 2
    assert hits["val"] == 1
    assert out["meta"]["retry"]["recovered"] == 1
    assert out["meta"]["status_mode"] == "mixed"  # val still fails
    assert out["batch"][0]["ok"] is True
    assert out["batch"][1]["ok"] is False


def test_fastapi_batch_retry_body_flags():
    app = FastAPI()
    ch = Channel.boot(
        app,
        config=ChannelConfig.development(secret="dev-secret-key-32chars-minimum!!!!"),
    )
    hits = {"n": 0}

    @ch.on(name="R.http", idempotent=True)
    def http_flaky():
        hits["n"] += 1
        if hits["n"] < 2:
            return Result.failure("rate_limited", "wait", retryable=True)
        return ch.done()

    client = TestClient(app)
    cap = ch.registry.mint("R.http", {})
    res = client.post(
        "/ux-channel/batch",
        json={
            "batch": [{"v": "1", "action": "R.http", "args": {}, "cap": cap}],
            "retry_retryable": True,
            "max_retries": 2,
            "retry_backoff_ms": 0,
        },
        headers={"X-Channel": "1", "Content-Type": "application/json"},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["ok"] is True
    assert body["meta"]["retry"]["recovered"] == 1
