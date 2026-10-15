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
import weakref
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import fakeredis
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from ux_channel import ChannelConfig, Result, toast
from ux_channel.asgi.fastapi import mount_channel
from ux_channel.devtools.ticket_revoke import get_revocation_list

try:
    from ux_channel.devtools.ticket_revoke import bind_ticket_close
except ImportError:  # pre-fix tree: missing symbol must fail the assertion, not collection
    bind_ticket_close = None
from ux_channel.host.idempotency import MemoryIdempotencyStore

try:
    from ux_channel.host.idempotency import IdempotencyCapacityError
except ImportError:
    IdempotencyCapacityError = None
from ux_channel.host.live import presence_count, presence_snapshot, touch_presence
from ux_channel.host.nonce import MemoryNonceStore
from ux_channel.host.registry import ActionRegistry
from ux_channel.host.stores import MemoryStateStore
from ux_channel.realtime.webrtc import MemoryRtcStore

try:
    from ux_channel.realtime.webrtc import await_rtc_inbox
except ImportError:
    await_rtc_inbox = None
from ux_channel.redis_extra import (
    RedisIdempotencyStore,
    RedisPushBackend,
    RedisRtcStore,
)
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
        "java\u00adscript:alert(1)",
        "java\u2060script:alert(1)",
        "java\U000F0000script:alert(1)",
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
        ["java\u00adscript:alert(1)", None],
        ["java\u2060script:alert(1)", None],
        ["java\U000F0000script:alert(1)", None],
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

    assert IdempotencyCapacityError is not None
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

    assert await_rtc_inbox is not None
    asyncio.run(_run())
    src = inspect.getsource(mount_channel)
    assert "await_rtc_inbox" in src
    assert "inbox.get(timeout" not in src


def test_reconnect_leave_drops_only_the_stale_connection() -> None:
    store = MemoryRtcStore(max_peers=4, peer_ttl_s=60, signal_ttl_s=60)
    assert "conn_id" in inspect.signature(store.poll).parameters
    assert "conn_id" in inspect.signature(store.leave).parameters
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

    assert bind_ticket_close is not None

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
    assert hasattr(backend, "_redis_topics")
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


def test_redis_leave_compare_and_delete_survives_the_replace_window() -> None:
    """WATCH/MULTI must reach EXEC, then keep a peer replaced before the commit.

    Known residual: eight aborted watches in a row give up. Leave then
    reports stale and the peer stays in the room until its TTL.
    """
    fake = fakeredis.FakeRedis(decode_responses=True)
    prefix = f"uidch:rtc:{uuid.uuid4().hex}:"
    store = RedisRtcStore(fake, max_peers=4, prefix=prefix)
    assert "conn_id" in inspect.signature(store.leave).parameters
    store.poll("room", "peer", conn_id="old")
    key = store._pk("room")

    original_eval = fake.eval

    def _eval_refuses_leave(*args, **kwargs):
        script = args[0] if args else ""
        if isinstance(script, str) and "HDEL" in script and "conn_id" in script:
            raise RuntimeError("lua disabled for leave")
        return original_eval(*args, **kwargs)

    fake.eval = _eval_refuses_leave  # type: ignore[method-assign]
    original_hget = fake.hget
    original_pipeline = fake.pipeline
    exec_calls = {"n": 0}

    def _pipeline(*args, **kwargs):
        pipe = original_pipeline(*args, **kwargs)
        original_execute = pipe.execute

        def _execute(*a, **k):
            if exec_calls["n"] == 0:
                exec_calls["n"] += 1
                current = original_hget(key, "peer")
                assert isinstance(current, str)
                assert "old" in current
                fake.hset(key, "peer", current.replace("old", "new", 1))
            return original_execute(*a, **k)

        pipe.execute = _execute  # type: ignore[method-assign]
        return pipe

    fake.pipeline = _pipeline  # type: ignore[method-assign]
    result = store.leave("room", "peer", conn_id="old")
    assert exec_calls["n"] >= 1, "WATCH fallback returned before EXEC"
    assert result.get("stale") is True
    kept = original_hget(key, "peer")
    assert isinstance(kept, str)
    assert "new" in kept
    assert "old" not in kept


def test_limit_exceeded_releases_idempotency_slot() -> None:
    store = MemoryIdempotencyStore(max_keys=10)
    reg = ActionRegistry(
        _SECRET, require_cap=False, idempotency_store=store, max_ops=0
    )
    calls = {"n": 0}

    def pay() -> Result:
        calls["n"] += 1
        return Result.success(toast("too many"))

    reg.register("Pay.go", pay)
    first = reg.dispatch(_intent("Pay.go", idempotency_key="k"))
    assert first.ok is False
    assert first.error is not None
    assert first.error.code == "payload_too_large"
    second = reg.dispatch(_intent("Pay.go", idempotency_key="k"))
    assert calls["n"] == 2
    assert second.error is not None
    assert second.error.code == "payload_too_large"


def test_cancelled_error_releases_idempotency_slot() -> None:
    store = MemoryIdempotencyStore(max_keys=10)
    reg = ActionRegistry(_SECRET, require_cap=False, idempotency_store=store)
    calls = {"n": 0}

    async def pay() -> Result:
        calls["n"] += 1
        raise asyncio.CancelledError()

    reg.register("Pay.go", pay)

    async def _run() -> None:
        with pytest.raises(asyncio.CancelledError):
            await reg.async_dispatch(_intent("Pay.go", idempotency_key="k"))
        assert calls["n"] == 1
        with pytest.raises(asyncio.CancelledError):
            await reg.async_dispatch(_intent("Pay.go", idempotency_key="k"))
        assert calls["n"] == 2

    asyncio.run(_run())


def test_idempotency_set_failure_is_not_success() -> None:
    store = MemoryIdempotencyStore(max_keys=10)
    reg = ActionRegistry(_SECRET, require_cap=False, idempotency_store=store)
    calls = {"n": 0}

    def pay() -> Result:
        calls["n"] += 1
        return Result.success()

    reg.register("Pay.go", pay)

    def _fail_set(key: str, result: dict, ttl_s: float = 3600, token: str | None = None) -> None:
        raise RuntimeError("store down")

    store.set = _fail_set  # type: ignore[method-assign]
    first = reg.dispatch(_intent("Pay.go", idempotency_key="k"))
    assert first.ok is False
    assert first.error is not None
    assert first.error.code == "unavailable"
    store.set = lambda key, result, ttl_s=3600, token=None: MemoryIdempotencyStore.set(  # type: ignore[method-assign]
        store, key, result, ttl_s=ttl_s, token=token
    )
    second = reg.dispatch(_intent("Pay.go", idempotency_key="k"))
    assert second.ok, second.error
    assert calls["n"] == 2


def test_nested_same_key_does_not_release_or_double_execute() -> None:
    store = MemoryIdempotencyStore(max_keys=10)
    reg = ActionRegistry(_SECRET, require_cap=False, idempotency_store=store)
    calls = {"n": 0}

    def pay() -> Result:
        calls["n"] += 1
        inner = reg.dispatch(_intent("Pay.go", idempotency_key="k"))
        assert inner.ok is False
        assert inner.error is not None
        assert inner.error.code == "unavailable"
        raced = store.claim("k")
        assert raced[0] == "pending", raced
        return Result.success()

    reg.register("Pay.go", pay)
    outer = reg.dispatch(_intent("Pay.go", idempotency_key="k"))
    assert outer.ok, outer.error
    assert calls["n"] == 1
    replay = reg.dispatch(_intent("Pay.go", idempotency_key="k"))
    assert replay.ok
    assert calls["n"] == 1


def test_cross_thread_same_owner_lock_errors_instead_of_deadlock() -> None:
    reg = ActionRegistry(_SECRET, require_cap=False)
    reg.sync_lock_timeout_s = 0.2
    done = threading.Event()
    results: list[Result] = []

    class Cart:
        def add(self) -> Result:
            worker = threading.Thread(target=self._other, daemon=True)
            worker.start()
            assert done.wait(1.5), "cross-thread re-dispatch deadlocked"
            return Result.success()

        def _other(self) -> None:
            results.append(reg.dispatch(_intent("Cart.add")))
            done.set()

    reg.register("Cart.add", Cart().add)
    outer = reg.dispatch(_intent("Cart.add"))
    assert outer.ok, outer.error
    assert results and results[0].ok is False
    assert results[0].error is not None
    assert "lock" in results[0].error.message


def test_different_sync_owners_do_not_block_each_other() -> None:
    reg = ActionRegistry(_SECRET, require_cap=False)
    entered = threading.Event()
    release = threading.Event()

    class Hold:
        def run(self) -> Result:
            entered.set()
            assert release.wait(2)
            return Result.success()

    class Other:
        def run(self) -> Result:
            return Result.success()

    reg.register("Hold.run", Hold().run)
    reg.register("Other.run", Other().run)
    threading.Thread(
        target=lambda: reg.dispatch(_intent("Hold.run")), daemon=True
    ).start()
    assert entered.wait(1)
    box: queue.Queue = queue.Queue()

    def _other() -> None:
        started = time.perf_counter()
        result = reg.dispatch(_intent("Other.run"))
        box.put((time.perf_counter() - started, result))

    threading.Thread(target=_other, daemon=True).start()
    try:
        elapsed, result = box.get(timeout=0.5)
    except queue.Empty:
        release.set()
        raise AssertionError("different owners blocked each other")
    release.set()
    assert result.ok
    assert elapsed < 0.4


def test_cross_worker_revoke_closes_socket_on_keepalive(monkeypatch: pytest.MonkeyPatch) -> None:
    """A denylist write with no in-process hook is noticed on the ping branch."""
    real_wait = asyncio.wait_for

    async def _fast_wait(awaitable, timeout=None):
        if timeout in (15.0, 20.0):
            timeout = 0.05
        return await real_wait(awaitable, timeout=timeout)

    monkeypatch.setattr(asyncio, "wait_for", _fast_wait)
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
    topic = f"shop.keep.{uuid.uuid4().hex[:12]}"
    ticket = sign_push_ticket(cfg, topic)
    client = TestClient(app)
    src = inspect.getsource(mount_channel)
    assert "is_revoked" in src
    with client.websocket_connect(f"/ux-channel/ws?ticket={ticket}") as ws:
        assert ws.receive_json()["type"] == "hello"
        ws.send_json({"type": "subscribe", "topic": topic})
        assert ws.receive_json()["type"] == "subscribed"
        from ux_channel.devtools import ticket_revoke as ticket_mod

        ticket_mod.get_revocation_list().store.revoke(ticket_mod._token_id(ticket))
        box: queue.Queue = queue.Queue()

        def _reader() -> None:
            try:
                while True:
                    box.put(("msg", ws.receive_json()))
            except Exception as exc:
                box.put(("closed", type(exc).__name__))

        threading.Thread(target=_reader, daemon=True).start()
        closed = False
        deadline = time.time() + 1.5
        while time.time() < deadline:
            try:
                kind, _payload = box.get(timeout=0.2)
            except queue.Empty:
                continue
            if kind == "closed":
                closed = True
                break
        assert closed, "keepalive branch left the socket open after is_revoked"


def test_sse_keepalive_stops_when_ticket_is_revoked(monkeypatch: pytest.MonkeyPatch) -> None:
    real_wait = asyncio.wait_for

    async def _fast_wait(awaitable, timeout=None):
        if timeout in (15.0, 20.0):
            timeout = 0.05
        return await real_wait(awaitable, timeout=timeout)

    monkeypatch.setattr(asyncio, "wait_for", _fast_wait)
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
    topic = f"shop.sse.{uuid.uuid4().hex[:12]}"
    ticket = sign_push_ticket(cfg, topic)
    client = TestClient(app)
    chunks: list[str] = []

    def _read() -> None:
        with client.stream("GET", f"/ux-channel/push/{topic}?ticket={ticket}") as resp:
            assert resp.status_code == 200
            for chunk in resp.iter_text():
                chunks.append(chunk)
                if sum(len(c) for c in chunks) > 200:
                    break

    worker = threading.Thread(target=_read, daemon=True)
    worker.start()
    time.sleep(0.15)
    from ux_channel.devtools import ticket_revoke as ticket_mod

    ticket_mod.get_revocation_list().store.revoke(ticket_mod._token_id(ticket))
    worker.join(1.5)
    assert not worker.is_alive(), "SSE keepalive continued after is_revoked"
    src = inspect.getsource(mount_channel)
    keepalive_at = src.find('yield ": keepalive')
    assert keepalive_at > 0
    assert "is_revoked" in src[keepalive_at - 400 : keepalive_at]


def test_cancel_during_sync_thread_runs_the_handler_once() -> None:
    """Cancelling async_dispatch must not free the slot while to_thread still runs."""
    store = MemoryIdempotencyStore(max_keys=10)
    reg = ActionRegistry(_SECRET, require_cap=False, idempotency_store=store)
    calls = {"n": 0}
    started = threading.Event()
    release = threading.Event()

    def pay() -> Result:
        calls["n"] += 1
        started.set()
        assert release.wait(2)
        return Result.success()

    reg.register("Pay.go", pay)

    async def _run() -> None:
        task = asyncio.create_task(
            reg.async_dispatch(_intent("Pay.go", idempotency_key="k"))
        )
        while not started.is_set():
            await asyncio.sleep(0.01)
        task.cancel()
        # The handler is still blocked. Cancellation must not finish the task
        # (and free the slot) before the worker returns.
        await asyncio.sleep(0.05)
        assert not task.done(), "slot released while the sync worker was still running"
        release.set()
        with pytest.raises(asyncio.CancelledError):
            await task
        second = await reg.async_dispatch(_intent("Pay.go", idempotency_key="k"))
        assert calls["n"] == 1
        assert second.ok, second.error

    asyncio.run(_run())


def test_slotted_owner_lock_is_not_bad_request() -> None:
    reg = ActionRegistry(_SECRET, require_cap=False)
    reg.sync_lock_timeout_s = 0.2
    entered = threading.Event()
    release = threading.Event()

    class Cart:
        __slots__ = ("label",)

        def __init__(self, label: str) -> None:
            self.label = label

        def add(self) -> Result:
            if self.label == "hold":
                entered.set()
                assert release.wait(2)
            return Result.success()

    hold = Cart("hold")
    other = Cart("other")
    with pytest.raises(TypeError):
        weakref.ref(hold)
    reg.register("Cart.hold", hold.add)
    reg.register("Cart.other", other.add)
    box: queue.Queue = queue.Queue()

    def _hold() -> None:
        box.put(reg.dispatch(_intent("Cart.hold")))

    threading.Thread(target=_hold, daemon=True).start()
    assert entered.wait(1), "slotted owner did not enter the handler"
    other_result = reg.dispatch(_intent("Cart.other"))
    release.set()
    held = box.get(timeout=1)
    assert held.ok, held.error
    assert other_result.ok is False
    assert other_result.error is not None
    assert other_result.error.code == "timeout"
    assert "lock" in other_result.error.message
    assert other_result.error.code != "bad_request"


def test_slotted_bound_action_self_is_not_bad_request() -> None:
    """ux-behavior style: the handler's __self__ is a slotted BoundAction."""

    class BoundAction:
        __slots__ = ("n",)

        def __init__(self) -> None:
            self.n = 0

        def run(self) -> Result:
            self.n += 1
            return Result.success()

    action = BoundAction()
    with pytest.raises(TypeError):
        weakref.ref(action)
    handler = action.run
    assert handler.__self__ is action
    reg = ActionRegistry(_SECRET, require_cap=False)
    reg.register("Go.run", handler)
    result = reg.dispatch(_intent("Go.run"))
    assert result.ok, result.error
    assert result.error is None or result.error.code != "bad_request"
    assert action.n == 1


def test_set_only_overwrites_its_own_pending_claim() -> None:
    store = MemoryIdempotencyStore(max_keys=10)
    status, _body, token = store.claim("k")
    assert status == "reserved"
    assert token
    params = inspect.signature(store.set).parameters
    foreign: dict = {}
    if "token" in params:
        foreign["token"] = "someone-else"
    try:
        store.set("k", {"ok": True, "ops": [], "n": 9}, **foreign)
    except Exception:
        pass
    raced = store.claim("k")
    assert raced[0] == "pending", raced
    own: dict = {}
    if "token" in params:
        own["token"] = token
    store.set("k", {"ok": True, "ops": [], "n": 1}, **own)
    saved = store.get("k")
    assert saved is not None
    assert saved.get("n") == 1
    try:
        store.set("k", {"ok": True, "ops": [], "n": 2}, **own)
    except Exception:
        pass
    assert store.get("k") is not None
    assert store.get("k").get("n") == 1


def test_two_redis_registries_run_one_idempotency_key_once() -> None:
    """Two registries sharing one Redis key run the handler once.

    The second call, while the first is in flight, is unavailable. A later
    retry returns the stored result and does not run the handler again.
    """
    fake = fakeredis.FakeRedis(decode_responses=True)
    prefix = f"uidch:idem:{uuid.uuid4().hex}:"
    store_a = RedisIdempotencyStore(fake, prefix=prefix)
    store_b = RedisIdempotencyStore(fake, prefix=prefix)
    reg_a = ActionRegistry(_SECRET, require_cap=False, idempotency_store=store_a)
    reg_b = ActionRegistry(_SECRET, require_cap=False, idempotency_store=store_b)
    calls = {"n": 0}
    entered = threading.Event()
    release = threading.Event()
    results: dict[str, Result] = {}

    def pay() -> Result:
        calls["n"] += 1
        entered.set()
        release.wait(2)
        return Result.success()

    reg_a.register("Pay.go", pay)
    reg_b.register("Pay.go", pay)

    def _run(name: str, reg: ActionRegistry) -> None:
        results[name] = reg.dispatch(_intent("Pay.go", idempotency_key="order-1"))

    worker_a = threading.Thread(target=_run, args=("a", reg_a), daemon=True)
    worker_a.start()
    assert entered.wait(2), "first worker did not enter the handler"
    worker_b = threading.Thread(target=_run, args=("b", reg_b), daemon=True)
    worker_b.start()
    worker_b.join(2)
    assert calls["n"] == 1
    assert not worker_b.is_alive(), "second registry ran the in-flight handler"
    release.set()
    worker_a.join(2)
    assert not worker_a.is_alive()
    assert results["a"].ok, results["a"].error
    assert results["b"].ok is False
    assert results["b"].error is not None
    assert results["b"].error.code == "unavailable"
    assert results["b"].error.retryable is True
    assert "in progress" in results["b"].error.message
    replay = reg_b.dispatch(_intent("Pay.go", idempotency_key="order-1"))
    assert replay.ok, replay.error
    assert calls["n"] == 1


def test_redis_full_idempotency_map_fails_closed() -> None:
    fake = fakeredis.FakeRedis(decode_responses=True)
    store = RedisIdempotencyStore(fake, max_keys=1)
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


def test_redis_failed_idempotent_call_releases_the_slot() -> None:
    fake = fakeredis.FakeRedis(decode_responses=True)
    store = RedisIdempotencyStore(fake, max_keys=1)
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


def test_redis_nested_same_key_does_not_release_or_double_execute() -> None:
    fake = fakeredis.FakeRedis(decode_responses=True)
    store = RedisIdempotencyStore(fake, max_keys=10)
    reg = ActionRegistry(_SECRET, require_cap=False, idempotency_store=store)
    calls = {"n": 0}

    def pay() -> Result:
        calls["n"] += 1
        inner = reg.dispatch(_intent("Pay.go", idempotency_key="k"))
        assert inner.ok is False
        assert inner.error is not None
        assert inner.error.code == "unavailable"
        raced = store.claim("k")
        assert raced[0] == "pending", raced
        return Result.success()

    reg.register("Pay.go", pay)
    outer = reg.dispatch(_intent("Pay.go", idempotency_key="k"))
    assert outer.ok, outer.error
    assert calls["n"] == 1
    replay = reg.dispatch(_intent("Pay.go", idempotency_key="k"))
    assert replay.ok
    assert calls["n"] == 1
