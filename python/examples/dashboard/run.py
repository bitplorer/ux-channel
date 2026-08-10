#!/usr/bin/env python3
"""Generate a working DX dashboard with the example Team extension.

Usage::

    cd /path/to/ux-channel
    PYTHONPATH=src python examples/dashboard/run.py
    # open reports/dx-example/dashboard.html
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from team_plugin import TeamOverview  # noqa: E402

from ux_channel.devtools.dashboard import (  # noqa: E402
    configure_dashboard,
    register_plugin,
    reset_dashboard_settings,
    run_dashboard_suite,
)


def main() -> int:
    reset_dashboard_settings()
    configure_dashboard(title="Example · ux-channel DX Dashboard")
    register_plugin(TeamOverview())

    out = ROOT / "reports" / "dx-example"
    model = run_dashboard_suite(
        out_dir=out,
        include_profile=True,
        rounds=12,
        warmup=2,
        profile_rounds=6,
        doctor={
            "ok": True,
            "hints": [
                "This is an example doctor payload.",
                "Replace with ch.doctor() in a real app.",
            ],
            "diagnose": {
                "environment": "example",
                "path": "/ux-channel",
                "actions": 3,
            },
        },
    )

    html = model["artifacts"]["html"]
    print("uxchannel DX dashboard example")
    print("=" * 40)
    print("Brand lines")
    print("  PyPI / pip : ux-channel")
    print("  import     : ux_channel")
    print("  CLI        : uxchannel")
    print("-" * 40)
    sec = model.get("sections") or {}
    print(f"  status    : {(sec.get('status') or {}).get('summary')}")
    print(f"  guidance  : {len((sec.get('guidance') or {}).get('hints') or [])} hints")
    perf = sec.get("performance") or {}
    if perf.get("available"):
        for lat in perf.get("latencies") or []:
            print(f"  perf      : {lat.get('name')} p95={lat.get('p95_ms')}")
    else:
        print("  perf      : (not sampled)")
    inv = sec.get("inventory") or {}
    print(f"  inventory : actions={inv.get('actions')} regions={inv.get('regions')}")
    print("-" * 40)
    print("plugins:")
    for plug in model.get("plugins") or []:
        print(f"  · {plug['id']}  (order={plug['order']})")
    print("-" * 40)
    print(f"open: {html}")
    print("model: dashboard.json (model schema 1 sections)")
    print("=" * 40)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
