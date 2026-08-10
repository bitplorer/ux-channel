#!/usr/bin/env python3
"""
uxchannel soak harness — CLI.

Design: docs/SOAK.md

Usage::

    # from repo root
    PYTHONPATH=src:. python scripts/soak/harness.py --mode inline --duration 10
    PYTHONPATH=src:. python scripts/soak/harness.py --mode http --base-url http://127.0.0.1:8765
    PYTHONPATH=src:. python scripts/soak/harness.py --list
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path

# repo root on path
_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
if str(_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(_ROOT / "src"))


def main(argv: list[str] | None = None) -> int:
    from scripts.soak.report import SoakReport, SloConfig
    from scripts.soak.scenarios import DEFAULT_SCENARIOS, SCENARIOS

    p = argparse.ArgumentParser(
        prog="soak-harness",
        description="uxchannel soak test harness (see docs/SOAK.md)",
    )
    p.add_argument(
        "--mode",
        choices=("inline", "http", "spawn"),
        default="inline",
        help="inline=ASGI in-process; http=BASE_URL; spawn=local uvicorn",
    )
    p.add_argument("--base-url", default=os.environ.get("BASE_URL", ""))
    p.add_argument("--secret", default=os.environ.get("SOAK_SECRET", ""))
    p.add_argument("--redis-url", default=os.environ.get("REDIS_URL", ""))
    p.add_argument("--duration", type=float, default=0.0, help="optional sustained loop seconds")
    p.add_argument("--pairs", type=int, default=20, help="rtc_mesh pairs")
    p.add_argument("--actions", type=int, default=100)
    p.add_argument("--peers-ws", type=int, default=16)
    p.add_argument(
        "--scenarios",
        default=",".join(DEFAULT_SCENARIOS),
        help="comma list or 'all'",
    )
    p.add_argument("--list", action="store_true", help="list scenarios and exit")
    p.add_argument("--report", default="soak-report.json")
    p.add_argument("--no-ticket", action="store_true", help="disable ticket requirement on app")
    p.add_argument("--max-peers", type=int, default=32)
    p.add_argument("--spawn-port", type=int, default=8765)
    args = p.parse_args(argv)

    if args.list:
        for name in SCENARIOS:
            print(name)
        return 0

    names = (
        list(SCENARIOS)
        if args.scenarios.strip() == "all"
        else [x.strip() for x in args.scenarios.split(",") if x.strip()]
    )
    for n in names:
        if n not in SCENARIOS:
            print(f"unknown scenario: {n}", file=sys.stderr)
            return 2

    slo = SloConfig.for_mode(args.mode)
    report = SoakReport(mode=args.mode, started_at=time.time(), slo=slo.__dict__)

    # --- open target ---
    client: Any
    secret = args.secret or "soak-test-secret-key-32chars-min!!"
    try:
        if args.mode == "inline":
            from scripts.soak.target import InlineTarget

            app_peers = args.max_peers
            if "room_full" in names:
                app_peers = min(app_peers, 6)  # ensure overflow reachable
            client = InlineTarget.create(
                secret=secret,
                redis_url=args.redis_url or None,
                webrtc_require_ticket=not args.no_ticket,
                webrtc_max_peers=app_peers,
            )
        elif args.mode == "http":
            if not args.base_url:
                print("--base-url or BASE_URL required for http mode", file=sys.stderr)
                return 2
            from scripts.soak.target import HttpTarget

            client = HttpTarget.create(args.base_url, secret=secret)
        else:
            from scripts.soak.target import SpawnTarget

            client = SpawnTarget.create(
                port=args.spawn_port,
                secret=secret,
                redis_url=args.redis_url or None,
            )
    except Exception as exc:
        print(f"target boot failed: {exc}", file=sys.stderr)
        return 2

    params = {
        "pairs": args.pairs,
        "n": args.actions,
        "max_peers": min(8, args.max_peers),  # room_full uses tight cap intent
    }

    try:
        rounds = 1
        deadline = time.time() + args.duration if args.duration > 0 else None
        while True:
            for name in names:
                fn = SCENARIOS[name]
                # per-scenario n overrides
                kw = dict(params)
                if name == "ticket_gate":
                    kw["n"] = max(20, args.actions // 2)
                if name == "rtc_ws":
                    kw["n"] = args.peers_ws
                if name == "rtc_mesh":
                    kw["pairs"] = args.pairs
                try:
                    result = fn(client, slo, **kw)
                except Exception as exc:
                    from scripts.soak.report import ScenarioResult

                    result = ScenarioResult(name=name, ok=False, error=str(exc))
                # keep worst result per name across rounds
                if rounds == 1:
                    report.scenarios.append(result)
                else:
                    prev = next(s for s in report.scenarios if s.name == name)
                    if not result.ok:
                        prev.ok = False
                        prev.detail = {"round": rounds, **(result.detail or {})}
                        prev.error = result.error
            if deadline is None or time.time() >= deadline:
                break
            rounds += 1

        # end metrics
        try:
            mr = client.get("/ux-channel/rtc/metrics")
            if mr.status_code == 200:
                report.metrics_end = mr.json()
        except Exception:
            pass
    finally:
        report.finished_at = time.time()
        try:
            client.close()
        except Exception:
            pass

    report.write(args.report)
    print(report.text())
    print(f"wrote {args.report}")
    return 0 if report.ok else 1


# typing
from typing import Any  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
