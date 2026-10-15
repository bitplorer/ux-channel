"""Deterministic in-process repros for the confirmed bug fixes.

Each test fails on the pre-fix behavior and passes once the fix holds.
Live sandbox only: no network peers, no external Redis.
"""

from __future__ import annotations

import asyncio
import inspect
import json
import queue
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import fakeredis
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from ux_channel import ChannelConfig, Result, toast
from ux_channel.asgi.fastapi import mount_channel
from ux_channel.devtools.ticket_revoke import (
    bind_ticket_close,
    get_revocation_list,
)
from ux_channel.host.idempotency import (
    IdempotencyCapacityError,
    MemoryIdempotencyStore,
)
from ux_channel.host.live import presence_count, presence_snapshot, touch_presence
from ux_channel.host.nonce import MemoryNonceStore
from ux_channel.host.registry import ActionRegistry
from ux_channel.host.stores import MemoryStateStore
from ux_channel.realtime.webrtc import MemoryRtcStore, await_rtc_inbox
from ux_channel.redis_extra import RedisPushBackend, RedisRtcStore
from ux_channel.security.push_security import sign_push_ticket
from ux_channel.security.ratelimit import MemoryRateLimiter, rate_limit_hook
from ux_channel.security.security import safe_href
from ux_channel.transport.push import get_push_bus

_SECRET = "dev-secret-key-32chars-minimum!!!!"
_STATIC = Path(__file__).resolve().parents[2] / "src" / "ux_channel" / "static"


def _intent(action: str, **extra: object) -> dict:
    body: dict = {"v": "1", "action": action, "args": {}}
    body.update(extra)
    return body


def test_safe_href_strips_controls_before_scheme_check() -> None:
    blocked = (
        "java\x00script:alert(1)",
        "java\tscript:alert(1)",
        "java\nscript:alert(1)",
        "java script:alert(1)",
        "\x00javascript:alert(1)",
        "javascript\x00:alert(1)",
        "jav\rasc\nript:alert(1)",
        "java\u200bscript:alert(1)",
    )
    for href in blocked:
        assert safe_href(href) is None, href
    assert safe_href("https://example.com/a") == "https://example.com/a"
    assert safe_href("/ok") == "/ok"
    assert safe_href("https://example.com/a b") == "https://example.com/a b"
    assert safe_href("https://example.com/a\x00b") == "https://example.com/ab"


def test_js_safe_href_strips_controls_before_scheme_check() -> None:
    import shutil

    binary = shutil.which("node")
    if not binary:
        pytest.skip("node is not installed")
    cases = [
        ["java\x00script:alert(1)", None],
        ["java\tscript:alert(1)", None],
        ["java script:alert(1)", None],
        ["\x00javascript:alert(1)", None],
        ["javascript\x00:alert(1)", None],
        ["jav\rasc\nript:alert(1)", None],
        ["https://example.com/a b", "https://example.com/a b"],
        ["/ok", "/ok"],
    ]
    script = r"""
const fs = require("fs");
const src = fs.readFileSync(process.argv[2], "utf8");
const cases = JSON.parse(process.argv[3]);
const start = src.indexOf("function safeHref");
if (start < 0) throw new Error("missing safeHref");
const brace = src.indexOf("{", start);
let depth = 0;
let end = -1;
for (let n = brace; n < src.length; n++) {
  if (src[n] === "{") depth++;
  else if (src[n] === "}") {
    depth--;
    if (depth === 0) { end = n + 1; break; }
  }
}
const fn = src.slice(src.lastIndexOf("\n", start) + 1, end);
const safeHref = new Function(fn + "\nreturn safeHref;")();
for (const [href, expected] of cases) {
  const got = safeHref(href);
  if (got !== expected) {
    console.error(JSON.stringify({ href, expected, got }));
    process.exit(1);
  }
}
"""
    import subprocess
    import tempfile

    for rel in ("ux-channel.js", "ux-peer-kernel.js"):
        target = _STATIC / rel
        with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False) as fh:
            fh.write(script)
            script_path = fh.name
        proc = subprocess.run(
            [binary, script_path, str(target), json.dumps(cases)],
            capture_output=True,
            text=True,
            check=False,
        )
        assert proc.returncode == 0, f"{rel}\n{proc.stdout}\n{proc.stderr}"


def test_once_cap_survives_rate_limit() -> None:
    reg = ActionRegistry(_SECRET, nonce_store=MemoryNonceStore(), require_cap=True)
    calls = {"n": 0}

    def pay() -> Result:
        calls["n"] += 1
        return Result.success()

    reg.register("Pay.once", pay)
    lim = MemoryRateLimiter(rate_per_minute=1, burst=1)
    reg.before(rate_limit_hook(lim))

    drain = reg.mint("Pay.once", {}, once=False)
    drained = reg.dispatch(_intent("Pay.once", cap=drain))
    assert drained.ok, drained.error

    once = reg.mint("Pay.once", {}, once=True)
    limited = reg.dispatch(_intent("Pay.once", cap=once))
    assert limited.ok is False
    assert limited.error is not None
    assert limited.error.code == "rate_limited"
    assert calls["n"] == 1

    with lim._lock:
        for bucket in lim._buckets.values():
            bucket.tokens = lim.burst
    retry = reg.dispatch(_intent("Pay.once", cap=once))
    assert retry.ok, retry.error
    assert calls["n"] == 2

    with lim._lock:
        for bucket in lim._buckets.values():
            bucket.tokens = lim.burst
    replay = reg.dispatch(_intent("Pay.once", cap=once))
    assert replay.ok is False
    assert replay.error is not None
    assert replay.error.code == "unauthorized"
    assert "capability replay (nonce)" in replay.error.message


def test_full_idempotency_map_fails_closed() -> None:
    store = MemoryIdempotencyStore(max_keys=1)
    reg = ActionRegistry(_SECRET, require_cap=False, idempotency_store=store)
    calls = {"n": 0}

    def pay() -> Result:
        calls["n"] += 1
        return Result.success()

    reg.register("Pay.go", pay)
    first = reg.dispatch(_intent("Pay.go", idempotency_key="k1"))
    again = reg.dispatch(_intent("Pay.go", idempotency_key="k1"))
    assert first.ok and again.ok
    assert calls["n"] == 1

    second = reg.dispatch(_intent("Pay.go", idempotency_key="k2"))
    assert second.ok is False
    assert second.error is not None
    assert second.error.code == "unavailable"
    assert "full" in second.error.message
    assert calls["n"] == 1

    direct = MemoryIdempotencyStore(max_keys=1)
    direct.set("a", {"ok": True, "ops": []})
    with pytest.raises(IdempotencyCapacityError):
        direct.set("b", {"ok": True, "ops": []})


def test_failed_idempotent_call_releases_the_slot() -> None:
    store = MemoryIdempotencyStore(max_keys=1)
    reg = ActionRegistry(_SECRET, require_cap=False, idempotency_store=store)
    calls = {"n": 0}

    def pay() -> Result:
        calls["n"] += 1
        if calls["n"] == 1:
            raise RuntimeError("payment failed")
        return Result.success()

    reg.register("Pay.go", pay)
    failed = reg.dispatch(_intent("Pay.go", idempotency_key="k1"))
    assert failed.ok is False
    nxt = reg.dispatch(_intent("Pay.go", idempotency_key="k2"))
    assert nxt.ok, nxt.error
    assert calls["n"] == 2


def test_idle_rtc_wait_does_not_pin_the_default_executor() -> None:
    async def _run() -> None:
        loop = asyncio.get_running_loop()
        loop.set_default_executor(ThreadPoolExecutor(max_workers=1))
        inbox: queue.Queue = queue.Queue()
        started = time.perf_counter()
        waiter = asyncio.create_task(await_rtc_inbox(inbox, idle_s=5.0, poll_s=0.01))
        await asyncio.sleep(0.05)

        def job() -> float:
            return time.perf_counter()

        finished = await loop.run_in_executor(None, job)
        assert finished - started < 0.5
        inbox.put({"type": "signal"})
        msg = await asyncio.wait_for(waiter, timeout=0.5)
        assert msg == {"type": "signal"}

    asyncio.run(_run())
    src = inspect.getsource(mount_channel)
    assert "await_rtc_inbox" in src
    assert "inbox.get(timeout" not in src


def test_reconnect_leave_drops_only_the_stale_connection() -> None:
    store = MemoryRtcStore(max_peers=4, peer_ttl_s=60, signal_ttl_s=60)
    old_q: queue.Queue = queue.Queue()
    new_q: queue.Queue = queue.Queue()
    store.poll("room", "peer", conn_id="old")
    store.subscribe("room", "peer", old_q)
    store.poll("room", "peer", conn_id="new")
    store.subscribe("room", "peer", new_q)
    store.unsubscribe("room", "peer", old_q)
    left = store.leave("room", "peer", conn_id="old")
    assert left.get("stale") is True
    roster = [p["id"] for p in store.poll("room", "peer", conn_id="new")["peers"]]
    assert roster == ["peer"]
    store.signal(
        "room",
        from_peer="peer",
        to_peer="peer",
        kind="ice",
        payload={"candidate": "x"},
    )
    assert new_q.get_nowait()["type"] == "signal"
    gone = store.leave("room", "peer")
    assert gone.get("stale") is not True
    assert store.poll("room", "keeper")["peers"] == [{"id": "keeper", "name": ""}]


def test_revoked_ticket_unsubscribes_before_the_next_push() -> None:
    bus = get_push_bus()
    topic = f"public.revoke.{uuid.uuid4().hex}"
    ticket = f"ticket-{uuid.uuid4().hex}"
    q: asyncio.Queue = asyncio.Queue()
    bus.subscribe(topic, q)

    def _close() -> None:
        bus.unsubscribe(topic, q)

    bind_ticket_close(ticket, _close)
    bus.publish(topic, Result.success(toast("first")))
    assert q.get_nowait()["ok"] is True
    get_revocation_list().revoke(ticket)
    bus.publish(topic, Result.success(toast("second")))
    with pytest.raises(asyncio.QueueEmpty):
        q.get_nowait()
    src = inspect.getsource(mount_channel)
    assert "bind_ticket_close" in src


def test_revoked_ticket_closes_the_push_socket() -> None:
    cfg = ChannelConfig.production(
        secret="prod-secret-key-32chars-minimum!!!!",
        allow_memory_stores=True,
        enforce_same_origin=False,
        require_channel_header=False,
        rate_limit_per_minute=0,
        ws_require_origin=False,
    )
    app = FastAPI()
    reg = ActionRegistry(
        cfg.secret,
        config=cfg,
        require_cap=cfg.require_cap,
        nonce_store=MemoryNonceStore(),
    )
    mount_channel(app, reg, config=cfg)
    topic = f"shop.rev.{uuid.uuid4().hex[:12]}"
    ticket = sign_push_ticket(cfg, topic)
    client = TestClient(app)
    with client.websocket_connect(f"/ux-channel/ws?ticket={ticket}") as ws:
        assert ws.receive_json()["type"] == "hello"
        ws.send_json({"type": "subscribe", "topic": topic})
        assert ws.receive_json()["type"] == "subscribed"
        get_push_bus().publish(topic, Result.success(toast("first-push")))
        seen = False
        for _ in range(6):
            msg = ws.receive_json()
            if msg.get("type") == "result" and "first-push" in json.dumps(msg):
                seen = True
                break
        assert seen
        box: queue.Queue = queue.Queue()

        def _reader() -> None:
            try:
                while True:
                    box.put(("msg", ws.receive_json()))
            except Exception as exc:
                box.put(("closed", type(exc).__name__))

        threading.Thread(target=_reader, daemon=True).start()
        get_revocation_list().revoke(ticket)
        get_push_bus().publish(topic, Result.success(toast("second-push")))
        closed = False
        deadline = time.time() + 2.0
        while time.time() < deadline:
            try:
                kind, payload = box.get(timeout=0.2)
            except queue.Empty:
                continue
            if kind == "closed":
                closed = True
                break
            assert "second-push" not in json.dumps(payload)
        assert closed, "socket stayed open after ticket revoke"


def test_concurrent_sync_clicks_keep_every_increment() -> None:
    store = MemoryStateStore()
    store.set("n", 0)
    reg = ActionRegistry(_SECRET, require_cap=False)

    def click() -> Result:
        current = int(store.get("n") or 0)
        time.sleep(0.01)
        store.set("n", current + 1)
        return Result.success()

    reg.register("Cart.sync", click)
    errors: list[BaseException] = []

    def _go() -> None:
        try:
            result = reg.dispatch(_intent("Cart.sync"))
            if not result.ok:
                errors.append(AssertionError(result.error))
        except BaseException as exc:
            errors.append(exc)

    threads = [threading.Thread(target=_go) for _ in range(32)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert errors == []
    assert store.get("n") == 32


def test_memory_rtc_max_peers_covers_signal() -> None:
    store = MemoryRtcStore(max_peers=1, peer_ttl_s=60, signal_ttl_s=60)
    store.poll("room", "a")
    with pytest.raises(OverflowError):
        store.poll("room", "b")
    with pytest.raises(OverflowError):
        store.signal(
            "room",
            from_peer="b",
            to_peer="a",
            kind="ice",
            payload={"candidate": "x"},
        )
    roster = [p["id"] for p in store.poll("room", "a")["peers"]]
    assert roster == ["a"]
    out = store.signal(
        "room",
        from_peer="a",
        to_peer="a",
        kind="ice",
        payload={"candidate": "y"},
    )
    assert out["ok"] is True


def test_redis_rtc_poll_cannot_exceed_max_peers() -> None:
    fake = fakeredis.FakeRedis(decode_responses=True)
    calls = {"n": 0}
    original = fake.eval

    def _eval(*args, **kwargs):
        calls["n"] += 1
        return original(*args, **kwargs)

    fake.eval = _eval  # type: ignore[method-assign]
    prefix = f"uidch:rtc:{uuid.uuid4().hex}:"
    store = RedisRtcStore(fake, max_peers=1, prefix=prefix)
    oks: list[str] = []
    full: list[str] = []
    other: list[BaseException] = []

    def _go(peer: str) -> None:
        try:
            store.poll("room", peer)
            oks.append(peer)
        except OverflowError:
            full.append(peer)
        except BaseException as exc:
            other.append(exc)

    threads = [threading.Thread(target=_go, args=(f"p{i}",)) for i in range(8)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert other == []
    assert len(oks) == 1
    assert len(full) == 7
    assert calls["n"] >= 1
    assert int(fake.hlen(f"{prefix}peers:room") or 0) == 1


def test_presence_expires_at_the_given_ttl(monkeypatch: pytest.MonkeyPatch) -> None:
    clock = {"t": 1_700_000_000.0}
    monkeypatch.setattr("ux_channel.host.live.time.time", lambda: clock["t"])
    topic = f"bug9.{uuid.uuid4().hex}"
    assert touch_presence(topic, "client", ttl_s=1) == 1
    clock["t"] += 1.01
    assert presence_count(topic) == 0
    assert topic not in presence_snapshot()

    held = f"bug9.held.{uuid.uuid4().hex}"
    assert touch_presence(held, "client", ttl_s=60) == 1
    clock["t"] += 59
    assert presence_count(held) == 1
    clock["t"] += 1.01
    assert presence_count(held) == 0


def test_redis_publisher_does_not_duplicate_pushes() -> None:
    fake = fakeredis.FakeRedis(decode_responses=True)
    backend = RedisPushBackend(fake)
    topic = f"public.dup.{uuid.uuid4().hex}"
    inbox: queue.Queue = queue.Queue()
    backend.subscribe_local(topic, inbox)
    deadline = time.time() + 1.0
    while time.time() < deadline and topic not in backend._redis_topics:
        time.sleep(0.01)
    assert topic in backend._redis_topics
    backend.publish(topic, {"ok": True, "n": 1})
    got: list[dict] = []
    quiet_until = time.time() + 0.8
    while time.time() < quiet_until:
        try:
            got.append(inbox.get(timeout=0.05))
        except queue.Empty:
            if got:
                break
    while True:
        try:
            got.append(inbox.get_nowait())
        except queue.Empty:
            break
    assert got == [{"ok": True, "n": 1}]
