
"""Backoff strategy math + batch integration."""

from __future__ import annotations

import random

from fastapi import FastAPI

from ux_channel import Channel, ChannelConfig
from ux_channel.backoff import BackoffPolicy, compute_backoff_ms, normalize_strategy
from ux_channel.batch import dispatch_batch
from ux_channel.types import Result


def test_normalize_aliases():
    assert normalize_strategy("exp") == "exponential"
    assert normalize_strategy("full_jitter") == "exponential_full_jitter"
    assert normalize_strategy("constant") == "fixed"


def test_fixed():
    assert compute_backoff_ms(1, strategy="fixed", base_ms=50) == 50
    assert compute_backoff_ms(3, strategy="fixed", base_ms=50) == 50


def test_linear():
    assert compute_backoff_ms(1, strategy="linear", base_ms=10) == 10
    assert compute_backoff_ms(3, strategy="linear", base_ms=10) == 30


def test_exponential():
    assert compute_backoff_ms(1, strategy="exponential", base_ms=50, factor=2) == 50
    assert compute_backoff_ms(2, strategy="exponential", base_ms=50, factor=2) == 100
    assert compute_backoff_ms(3, strategy="exponential", base_ms=50, factor=2) == 200
    # cap
    assert compute_backoff_ms(10, strategy="exponential", base_ms=50, max_ms=120, factor=2) == 120


def test_full_jitter_bounds():
    rng = random.Random(0)
    for _ in range(20):
        d = compute_backoff_ms(
            3, strategy="exponential_full_jitter", base_ms=50, factor=2, max_ms=1000, rng=rng
        )
        # exp = 200
        assert 0 <= d <= 200


def test_equal_jitter_bounds():
    rng = random.Random(1)
    for _ in range(20):
        d = compute_backoff_ms(
            2, strategy="exponential_equal_jitter", base_ms=100, factor=2, rng=rng
        )
        # exp = 200 → [100, 200]
        assert 100 <= d <= 200


def test_policy_to_meta():
    p = BackoffPolicy(strategy="exponential", base_ms=40, max_ms=1000, factor=2)
    m = p.to_meta()
    assert m["strategy"] == "exponential"
    assert m["base_ms"] == 40


def test_batch_records_exponential_delays():
    ch = Channel.boot(
        FastAPI(),
        config=ChannelConfig.development(secret="dev-secret-key-32chars-minimum!!!!"),
    )
    hits = {"n": 0}

    @ch.on(name="B.exp", idempotent=True)
    def exp_fail():
        hits["n"] += 1
        return Result.failure("rate_limited", "x", retryable=True)

    out = dispatch_batch(
        ch.registry,
        [{"v": "1", "action": "B.exp", "args": {}, "cap": ch.registry.mint("B.exp", {})}],
        retry_retryable=True,
        max_retries=3,
        retry_backoff_ms=10,
        retry_backoff_strategy="exponential",
        retry_backoff_factor=2,
        retry_backoff_max_ms=1000,
    )
    # 1 + 3 attempts = 4 total, delays for 3 retries: 10, 20, 40
    assert hits["n"] == 4
    delays = out["meta"]["retry"]["delays_ms"][0]
    assert delays == [10.0, 20.0, 40.0]
    assert out["meta"]["retry"]["backoff"]["strategy"] == "exponential"
    assert out["meta"]["retry"]["exhausted"] == 1


def test_batch_fixed_still_works():
    ch = Channel.boot(
        FastAPI(),
        config=ChannelConfig.development(secret="dev-secret-key-32chars-minimum!!!!"),
    )
    hits = {"n": 0}

    @ch.on(name="B.fix", idempotent=True)
    def fix():
        hits["n"] += 1
        if hits["n"] < 2:
            return Result.failure("timeout", "t", retryable=True)
        return ch.done()

    out = dispatch_batch(
        ch.registry,
        [{"v": "1", "action": "B.fix", "args": {}, "cap": ch.registry.mint("B.fix", {})}],
        retry_retryable=True,
        max_retries=1,
        retry_backoff_ms=0,  # no sleep in tests
        retry_backoff_strategy="fixed",
    )
    assert out["ok"]
    assert out["meta"]["retry"]["delays_ms"][0] == [0.0]
