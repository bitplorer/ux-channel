"""A push published from another thread wakes the reader's loop at once.

Before the fix the item sat in the ``asyncio.Queue`` until the reader's
timeout woke the loop (15 s SSE, 20 s WS in production).
"""

from __future__ import annotations

import asyncio
import threading
import time
import uuid

import fakeredis

from ux_channel.redis_extra import RedisPushBackend
from ux_channel.transport.push import MemoryPushBackend

DELAY = 0.2
TIMEOUT = 3.0


async def _latency(q: asyncio.Queue, publish) -> float:
    def later() -> None:
        time.sleep(DELAY)  # the loop is asleep in select() by now
        publish()

    threading.Thread(target=later, daemon=True).start()
    t0 = time.monotonic() + DELAY
    await asyncio.wait_for(q.get(), TIMEOUT)
    return time.monotonic() - t0


def test_memory_publish_from_worker_thread_wakes_reader() -> None:
    async def run() -> float:
        be = MemoryPushBackend()
        q: asyncio.Queue = asyncio.Queue(maxsize=8)
        be.subscribe_local("t", q)
        return await _latency(q, lambda: be.publish("t", {"ok": True}))

    assert asyncio.run(run()) < 1.0


def test_redis_listener_thread_wakes_reader() -> None:
    fake = fakeredis.FakeRedis(decode_responses=True)
    topic = f"lat.{uuid.uuid4().hex}"

    async def run() -> float:
        be = RedisPushBackend(fake)
        q: asyncio.Queue = asyncio.Queue(maxsize=8)
        be.subscribe_local(topic, q)
        while topic not in be._redis_topics:
            await asyncio.sleep(0.01)
        await asyncio.sleep(0.1)  # listener thread is polling
        return await _latency(q, lambda: fake.publish(be._ch(topic), '{"ok": true}'))

    assert asyncio.run(run()) < 1.0


def test_publish_after_reader_loop_closed_is_dropped() -> None:
    be = MemoryPushBackend()

    async def subscribe() -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue(maxsize=8)
        be.subscribe_local("t", q)
        return q

    asyncio.run(subscribe())
    result: list[int] = []
    t = threading.Thread(target=lambda: result.append(be.publish("t", {"ok": True})))
    t.start()
    t.join()
    assert result == [0]
