"""Redis backends — multi-worker stores via fakeredis (no real Redis required)."""

from __future__ import annotations

import fakeredis
import pytest
from redis.crc import key_slot
from redis.exceptions import ResponseError

import ux_channel.redis_extra as redis_extra
from ux_channel.host.idempotency import IdempotencyCapacityError
from ux_channel.protocol import serde as _serde
from ux_channel.redis_extra import (
    RedisIdempotencyStore,
    RedisNonceStore,
    RedisPushBackend,
    RedisRateLimiter,
    RedisStateStore,
)
from ux_channel.transport.push import PushBus, set_push_bus, get_push_bus
from ux_channel.protocol.types import Result
from ux_channel.protocol.ops import toast
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


def test_redis_idempotency_claim_is_token_checked(r):
    store = RedisIdempotencyStore(r, max_keys=1)
    other = RedisIdempotencyStore(r, max_keys=1)
    status, body, token = store.claim("k", ttl_s=60)
    assert status == "reserved"
    assert body is None
    assert token
    assert store.get("k") is None

    raced = other.claim("k")
    assert raced[0] == "pending"
    other.release("k", "someone-else")
    assert store.claim("k")[0] == "pending"
    with pytest.raises(RuntimeError, match="does not own"):
        store.set("k", {"ok": True, "ops": [], "n": 9}, token="someone-else")
    with pytest.raises(RuntimeError, match="does not own"):
        store.set("k", {"ok": True, "ops": [], "n": 9})
    assert store.claim("k")[0] == "pending"

    store.set("k", {"ok": True, "ops": [], "n": 1}, ttl_s=60, token=token)
    saved = store.get("k")
    assert saved is not None
    assert saved["n"] == 1
    store.set("k", {"ok": True, "ops": [], "n": 2}, token=token)
    assert store.get("k")["n"] == 1
    store.set("k", {"ok": True, "ops": [], "n": 3}, ttl_s=60)
    assert store.get("k")["n"] == 3
    hit, hit_body, hit_token = store.claim("k")
    assert hit == "hit"
    assert hit_body is not None and hit_body["n"] == 3
    assert hit_token is None
    store.release("k", token)
    assert store.get("k")["n"] == 3
    r.set("unrelated", "1")

    with pytest.raises(IdempotencyCapacityError):
        store.claim("other")
    with pytest.raises(IdempotencyCapacityError):
        store.set("fresh", {"ok": True, "ops": []})

    lost = RedisIdempotencyStore(r, prefix="uidch:idem:lost:", max_keys=2)
    lost_status, _, lost_token = lost.claim("solo", ttl_s=60)
    assert lost_status == "reserved"
    assert lost_token
    lost.release("solo", lost_token)
    with pytest.raises(RuntimeError, match="lost"):
        lost.set("solo", {"ok": True, "ops": []}, token=lost_token)
    assert lost.get("solo") is None

    freed = RedisIdempotencyStore(r, prefix="uidch:idem:cap:", max_keys=1)
    cap_status, _, cap_token = freed.claim("a", ttl_s=60)
    assert cap_status == "reserved"
    assert cap_token
    with pytest.raises(IdempotencyCapacityError):
        freed.claim("b")
    freed.release("a", cap_token)
    again, _, again_token = freed.claim("b", ttl_s=60)
    assert again == "reserved"
    assert again_token


def test_redis_idempotency_bytes_client():
    raw = fakeredis.FakeRedis(decode_responses=False)
    store = RedisIdempotencyStore(raw, max_keys=2)
    status, body, token = store.claim("k", ttl_s=30)
    assert status == "reserved"
    assert body is None and token
    store.set("k", {"ok": True, "ops": [], "n": 4}, token=token, ttl_s=30)
    assert store.get("k")["n"] == 4
    hit = store.claim("k")
    assert hit[0] == "hit" and hit[1] is not None and hit[1]["n"] == 4


def test_redis_idempotency_data_key_shares_slot_with_index():
    """Hash tag on the data key must match the capacity index slot."""
    prefix = "uidch:idem:"
    store = RedisIdempotencyStore(
        fakeredis.FakeRedis(decode_responses=True), prefix=prefix
    )
    data = store._redis_key("order-1")
    index = redis_extra._idem_index(prefix)
    assert data == "{" + prefix + "}" + "order-1"
    assert index == "{" + prefix + "}.cap"
    assert key_slot(data.encode()) == key_slot(index.encode())
    assert "EXISTS" not in redis_extra._IDEM_CLAIM_LUA
    assert "EXISTS" not in redis_extra._IDEM_SET_LUA
    assert "ZREMRANGEBYSCORE" in redis_extra._IDEM_CLAIM_LUA
    assert "KEEPTTL" in redis_extra._IDEM_SET_LUA


def test_legacy_untagged_result_hits_without_eval():
    fake = fakeredis.FakeRedis(decode_responses=True)
    prefix = "uidch:idem:"
    store = RedisIdempotencyStore(fake, prefix=prefix)
    fake.set(
        prefix + "order-1",
        _serde.dumps({"ok": True, "ops": [], "n": 7}),
    )

    def _eval_must_not_run(*args, **kwargs):
        raise AssertionError("legacy hit must stay outside the script")

    fake.eval = _eval_must_not_run  # type: ignore[method-assign]
    assert store.get("order-1")["n"] == 7
    status, body, token = store.claim("order-1")
    assert status == "hit"
    assert body is not None and body["n"] == 7
    assert token is None
    assert fake.get("{" + prefix + "}order-1") is None


def test_tokenless_refresh_keeps_ttl_and_score():
    fake = fakeredis.FakeRedis(decode_responses=True)
    prefix = "uidch:idem:"
    store = RedisIdempotencyStore(fake, prefix=prefix)
    status, _, token = store.claim("k", ttl_s=40)
    assert status == "reserved" and token
    store.set("k", {"ok": True, "ops": [], "n": 1}, ttl_s=40, token=token)
    data = "{" + prefix + "}k"
    index = "{" + prefix + "}.cap"
    ttl_before = int(fake.ttl(data))
    score_before = fake.zscore(index, data)
    assert ttl_before > 1
    assert score_before is not None
    store.set("k", {"ok": True, "ops": [], "n": 2}, ttl_s=4000)
    assert store.get("k")["n"] == 2
    assert int(fake.ttl(data)) <= ttl_before
    assert fake.zscore(index, data) == score_before


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
    from ux_channel.host.factory import create_channel
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

    cap = ch.registry.mint("Pay.once", {}, once=True)
    r1 = ch.registry.dispatch({"v": "1", "action": "Pay.once", "args": {}, "cap": cap})
    r2 = ch.registry.dispatch({"v": "1", "action": "Pay.once", "args": {}, "cap": cap})
    assert r1.ok
    assert not r2.ok
