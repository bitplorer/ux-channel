"""Batch dispatch + bulkhead concurrency tests."""

from __future__ import annotations

import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

from fastapi import FastAPI
from fastapi.testclient import TestClient

from ux_channel import ActionRegistry, Result, toast
from ux_channel.asgi.fastapi import mount_channel
from ux_channel.batch import dispatch_batch, dispatch_batch_async
from ux_channel.bulkhead import ConcurrencyLimiter, install_bulkhead
from ux_channel.config import ChannelConfig
from ux_channel.types import Intent

SECRET = "dev-secret-key-32chars-minimum!!!!"


def test_batch_sync_merge():
    reg = ActionRegistry(secret=SECRET, require_cap=True)
    reg.register("A.x", lambda: Result.success(toast("a")))
    reg.register("B.y", lambda: Result.success(toast("b")))
    items = [
        {"v": "1", "action": "A.x", "args": {}, "cap": reg.mint("A.x", {})},
        {"v": "1", "action": "B.y", "args": {}, "cap": reg.mint("B.y", {})},
    ]
    out = dispatch_batch(reg, items)
    assert out["ok"] is True
    assert len(out["batch"]) == 2
    assert len(out["ops"]) == 2


def test_batch_too_large():
    reg = ActionRegistry(secret=SECRET, require_cap=False)
    reg.register("A.x", lambda: Result.success())
    items = [{"v": "1", "action": "A.x", "args": {}} for _ in range(20)]
    out = dispatch_batch(reg, items, max_items=4)
    assert out["ok"] is False
    assert out["error"]["code"] == "payload_too_large"


def test_batch_http_endpoint():
    app = FastAPI()
    cfg = ChannelConfig.development(
        secret=SECRET, rate_limit_per_minute=0, enforce_same_origin=False
    )
    reg = ActionRegistry.from_config(cfg)
    reg.register("Ping.a", lambda: Result.success(toast("1")))
    reg.register("Ping.b", lambda: Result.success(toast("2")))
    mount_channel(app, reg, config=cfg)
    c = TestClient(app)
    body = {
        "v": "1",
        "batch": [
            {"v": "1", "action": "Ping.a", "args": {}, "cap": reg.mint("Ping.a", {})},
            {"v": "1", "action": "Ping.b", "args": {}, "cap": reg.mint("Ping.b", {})},
        ],
    }
    r = c.post(
        "/ux-channel/batch",
        json=body,
        headers={"X-Channel": "1"},
    )
    assert r.status_code == 200
    assert r.json()["ok"] is True
    assert len(r.json()["batch"]) == 2


def test_bulkhead_rejects_over_capacity():
    reg = ActionRegistry(secret=SECRET, require_cap=False)
    lim = install_bulkhead(reg, max_in_flight=2)
    gate = threading.Event()
    started = threading.Barrier(3)

    @reg.action("Hold.x")
    def hold():
        started.wait(timeout=2)
        gate.wait(timeout=2)
        return Result.success(toast("done"))

    results = []

    def run():
        results.append(reg.dispatch(Intent(action="Hold.x", args={})).ok)

    threads = [threading.Thread(target=run) for _ in range(4)]
    for t in threads:
        t.start()
    # let 2 enter, 2 may be rejected depending on timing
    time.sleep(0.05)
    # force third/fourth to attempt while 2 held
    try:
        started.wait(timeout=1)
    except Exception:
        pass
    # Two should be in flight; extras rejected
    time.sleep(0.05)
    gate.set()
    for t in threads:
        t.join(timeout=3)
    stats = lim.stats()
    assert stats["rejected"] >= 1 or sum(1 for x in results if not x) >= 1
    assert stats["accepted"] >= 2


def test_load_burst_actions():
    """Sudden burst of 200 sequential-cap dispatches must stay correct."""
    reg = ActionRegistry(secret=SECRET, require_cap=True)
    counter = {"n": 0}
    lock = threading.Lock()

    @reg.action("Load.tick")
    def tick():
        with lock:
            counter["n"] += 1
            n = counter["n"]
        return Result.success(toast(str(n)))

    def one(_: int) -> bool:
        cap = reg.mint("Load.tick", {})
        r = reg.dispatch(Intent(action="Load.tick", args={}, cap=cap))
        return r.ok

    with ThreadPoolExecutor(32) as ex:
        oks = list(ex.map(one, range(200)))
    assert all(oks)
    assert counter["n"] == 200


def test_load_http_channel_scaling():
    """HTTP POST /ux-channel/action under concurrent clients."""
    app = FastAPI()
    cfg = ChannelConfig.development(
        secret=SECRET,
        rate_limit_per_minute=0,
        enforce_same_origin=False,
        require_channel_header=False,
    )
    reg = ActionRegistry.from_config(cfg)
    install_bulkhead(reg, max_in_flight=64)
    hits = {"n": 0}
    lock = threading.Lock()

    @reg.action("Http.load")
    def load():
        with lock:
            hits["n"] += 1
        return Result.success(toast("ok"))

    mount_channel(app, reg, config=cfg)
    c = TestClient(app)

    def post(_: int) -> int:
        cap = reg.mint("Http.load", {})
        r = c.post(
            "/ux-channel/action",
            json={"v": "1", "action": "Http.load", "args": {}, "cap": cap},
        )
        return r.status_code

    with ThreadPoolExecutor(40) as ex:
        codes = list(ex.map(post, range(150)))
    assert codes.count(200) == 150
    assert hits["n"] == 150
    bh = reg._bulkhead.stats()  # type: ignore[attr-defined]
    assert bh["completed"] == 150
    assert bh["rejected"] == 0
