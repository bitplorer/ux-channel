#!/usr/bin/env python3
"""
Load / burst test for uxchannel action endpoint.

Usage::

    python scripts/load_test_channel.py
    python scripts/load_test_channel.py --workers 64 --requests 2000 --max-in-flight 128

Reports latency percentiles, success rate, bulkhead rejections.
"""

from __future__ import annotations

import argparse
import statistics
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

from fastapi import FastAPI
from fastapi.testclient import TestClient

from ux_channel import Result, toast
from ux_channel.asgi.fastapi import mount_channel
from ux_channel.bulkhead import install_bulkhead
from ux_channel.config import ChannelConfig
from ux_channel.registry import ActionRegistry


def build_app(max_in_flight: int, secret: str):
    app = FastAPI()
    cfg = ChannelConfig.development(
        secret=secret,
        rate_limit_per_minute=0,
        enforce_same_origin=False,
        require_channel_header=False,
    )
    reg = ActionRegistry.from_config(cfg)
    install_bulkhead(reg, max_in_flight=max_in_flight)

    @reg.action("Load.ping")
    def ping(x: int = 0):
        # tiny synthetic work
        _ = sum(range(50))
        return Result.success(toast(f"ok:{x}"))

    mount_channel(app, reg, config=cfg)
    return app, reg


def main() -> int:
    p = argparse.ArgumentParser(description="uxchannel load test")
    p.add_argument("--workers", type=int, default=32)
    p.add_argument("--requests", type=int, default=500)
    p.add_argument("--max-in-flight", type=int, default=64)
    p.add_argument("--secret", default="load-test-secret-key-32chars-min!!")
    args = p.parse_args()

    app, reg = build_app(args.max_in_flight, args.secret)
    client = TestClient(app)
    latencies: list[float] = []
    codes: list[int] = []

    def one(i: int) -> tuple[int, float]:
        cap = reg.sign("Load.ping", {"x": i % 10})
        t0 = time.perf_counter()
        r = client.post(
            "/ux-channel/action",
            json={
                "uid": "1",
                "action": "Load.ping",
                "args": {"x": i % 10},
                "cap": cap,
            },
        )
        dt = (time.perf_counter() - t0) * 1000
        return r.status_code, dt

    t_wall0 = time.perf_counter()
    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        futs = [ex.submit(one, i) for i in range(args.requests)]
        for f in as_completed(futs):
            code, ms = f.result()
            codes.append(code)
            latencies.append(ms)
    wall = time.perf_counter() - t_wall0

    latencies.sort()
    def pct(p: float) -> float:
        if not latencies:
            return 0.0
        idx = min(len(latencies) - 1, int(p * (len(latencies) - 1)))
        return latencies[idx]

    ok = codes.count(200)
    limited = sum(1 for c in codes if c == 429)
    bh = getattr(reg, "_bulkhead", None)
    print("=== uxchannel load test ===")
    print(f"workers={args.workers} requests={args.requests} max_in_flight={args.max_in_flight}")
    print(f"wall_s={wall:.3f} rps={args.requests / wall:.1f}")
    print(f"http_200={ok} http_429={limited} other={len(codes) - ok - limited}")
    print(
        f"latency_ms p50={pct(0.50):.2f} p95={pct(0.95):.2f} p99={pct(0.99):.2f} "
        f"max={latencies[-1]:.2f} mean={statistics.fmean(latencies):.2f}"
    )
    if bh:
        print(f"bulkhead={bh.stats()}")
    # success criterion: all completed, no crashes; 429 only if over capacity intentionally
    return 0 if ok + limited == args.requests else 1


if __name__ == "__main__":
    raise SystemExit(main())
