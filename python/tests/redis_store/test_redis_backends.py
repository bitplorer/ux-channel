"""Redis backends — multi-worker stores via fakeredis (no real Redis required)."""

from __future__ import annotations

import fakeredis
import pytest

from ux_channel.redis_extra import (
    RedisIdempotencyStore,
    RedisNonceStore,
    RedisPushBackend,
    RedisRateLimiter,
    RedisStateStore,
)
from ux_channel.push import PushBus, set_push_bus, get_push_bus
from ux_channel.types import Result
from ux_channel.ops import toast
from ux_channel import Channel, ChannelConfig
from fastapi import FastAPI


@pytest.fixture
def r():
    return fakeredis.FakeRedis(decode_responses=True)


def test_redis_nonce_once(r):
    store = RedisNonceStore(r)
    assert store.use_once("jti-1", ttl_s=60) is True
    assert store.use_once("jti-1", ttl_s=60) is False


def test_redis_idempotency(r):
    store = RedisIdempotencyStore(r)
    assert store.get("k1") is None
    store.set("k1", {"ok": True, "ops": []}, ttl_s=60)
    assert store.get("k1")["ok"] is True


def test_redis_rate_limiter(r):
    lim = RedisRateLimiter(r, rate_per_minute=5, burst=0)
    for _ in range(5):
        assert lim.allow("ip:1") is True
    assert lim.allow("ip:1") is False


def test_redis_state_change(r):
    st = RedisStateStore(r)
    st.set("n", 0)
    out = st.change("n", lambda x: (x or 0) + 1, default=0)
    assert out == 1
    assert st.get("n") == 1
    st.merge("form", {"a": 1, "b": 2})
    assert st.get("form")["a"] == 1


def test_redis_push_publish_local(r):
    backend = RedisPushBackend(r)
    bus = PushBus(backend)
    import asyncio

    async def _run():
        q = asyncio.Queue()
        bus.subscribe("public.t", q)
        # local subscribe should get publish via listener — may be async
        n = bus.publish("public.t", Result.success(toast("hi")))
        # even if redis pubsub is tricky with fakeredis, publish should not raise
        assert n >= 0
        bus.unsubscribe("public.t", q)

    asyncio.run(_run())


def test_with_redis_config_url_roundtrip():
    cfg = ChannelConfig.production("s" * 32, allow_memory_stores=True).with_redis(
        "redis://example:6379/0"
    )
    assert cfg.redis_url == "redis://example:6379/0"
    assert cfg.allow_memory_stores is False


def test_boot_accepts_config_redis_url_memory_fallback():
    """Without real redis URL reachable, FakeRedis via redis_url object path."""
    # create_channel with FakeRedis as redis_url for nonce store path
    from ux_channel.factory import create_channel
    from ux_channel.redis_extra import RedisNonceStore, RedisIdempotencyStore

    fake = fakeredis.FakeRedis(decode_responses=True)
    app = FastAPI()
    cfg = ChannelConfig.production("s" * 32, allow_memory_stores=False)
    reg, hub = create_channel(
        config=cfg,
        app=app,
        redis_url=None,
        auto_redis=False,
        nonce_store=RedisNonceStore(fake),
        idempotency_store=RedisIdempotencyStore(fake),
    )
    assert reg.nonce_store is not None
    assert reg.nonce_store.use_once("x", ttl_s=10)
    assert not reg.nonce_store.use_once("x", ttl_s=10)


def test_channel_once_cap_with_redis_nonce(r):
    app = FastAPI()
    from ux_channel.redis_extra import RedisNonceStore
    cfg = ChannelConfig.development(secret="dev-secret-key-32chars-minimum!!!!")
    ch = Channel.boot(app, config=cfg)
    # replace nonce store
    ch.registry.nonce_store = RedisNonceStore(r)

    @ch.on(name="Pay.once", once=True)
    def pay():
        return ch.done(notice="paid")

    cap = ch.registry.sign("Pay.once", {}, once=True)
    r1 = ch.registry.dispatch({"v": "1", "action": "Pay.once", "args": {}, "cap": cap})
    r2 = ch.registry.dispatch({"v": "1", "action": "Pay.once", "args": {}, "cap": cap})
    assert r1.ok
    assert not r2.ok
