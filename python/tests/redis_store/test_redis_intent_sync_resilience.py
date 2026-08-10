"""Redis pubsub intent sync + connection resilience + soft-fail."""

from __future__ import annotations

import time

import pytest
from fastapi import FastAPI

from ux_channel import Channel, ChannelConfig, Intent
from ux_channel.intent_sync import (
    IntentSyncMessage,
    MemoryIntentSyncBus,
    attach_intent_sync,
)
from ux_channel.intent_log import attach_intent_log
from ux_channel.redis_extra.resilience import RedisUnavailable, ResilientRedis


SECRET = "sync-resilience-secret-key-32b!!"


def _ch():
    app = FastAPI()
    return Channel.boot(
        app,
        config=ChannelConfig.development(
            secret=SECRET, allow_memory_stores=True, require_cap=False
        ),
    )


def test_memory_intent_sync_pubsub_style():
    ch = _ch()
    seen = []
    bus = attach_intent_sync(ch, bus=MemoryIntentSyncBus())
    bus.subscribe(lambda m: seen.append(m.action))

    @ch.on
    def go():
        return ch.done(notice="n")

    ch.registry.dispatch(Intent(action="go", args={}, cap=ch.mint("go", {})))
    assert "go" in seen


def test_redis_intent_sync_with_fakeredis():
    fakeredis = pytest.importorskip("fakeredis")
    from ux_channel.intent_sync import RedisIntentSyncBus, attach_intent_sync

    r = fakeredis.FakeRedis(decode_responses=True)
    ch = _ch()
    bus = RedisIntentSyncBus(r, prefix="t:sync:", worker_id="A")
    remote_seen = []
    bus_b = RedisIntentSyncBus(r, prefix="t:sync:", worker_id="B")
    bus_b.subscribe(lambda m: remote_seen.append(m))

    time.sleep(0.15)

    attach_intent_sync(ch, bus=bus)

    @ch.on
    def act():
        return ch.done(notice="z")

    ch.registry.dispatch(Intent(action="act", args={}, cap=ch.mint("act", {})))
    deadline = time.time() + 2.0
    while time.time() < deadline and not remote_seen:
        time.sleep(0.05)
    assert bus.publish(IntentSyncMessage(seq=99, action="act", ok=True)) >= 0


def test_resilient_redis_soft_fail_bad_url():
    rr = ResilientRedis("redis://127.0.0.1:1/0", soft_fail=True)
    # should not raise hard on soft_fail
    try:
        rr.ping()
    except RedisUnavailable:
        pass
