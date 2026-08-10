#!/usr/bin/env python3
"""Short soak: multi-claim I/O gate + adapters (D4). Not a public API."""
from __future__ import annotations

import random
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ux_channel.io_adapters import LabDutAdapter, LightsAdapter, ScannerAdapter
from ux_channel.foundations.io_channel import (
    IoChannelError,
    IoGate,
    attach_io_audit,
    claim_from_ticket_claims,
    run_checked,
)
from ux_channel.foundations.quantity import Quantity


def main() -> int:
    gate = IoGate()
    bag = type("B", (), {})()
    audit = attach_io_audit(bag)
    scanner, lights, lab = ScannerAdapter(), LightsAdapter(), LabDutAdapter()
    for a in (scanner, lights, lab):
        gate.register(a.describe())

    n_ok = n_fail = 0
    t0 = time.time()
    for i in range(200):
        kind = random.choice(["scan", "lights", "flash", "bad"])
        try:
            if kind == "scan":
                claim = claim_from_ticket_claims(
                    {"room": "pos", "peer_id": f"p{i}", "scopes": ["scan", "pos"]}
                )
                scanner.inject(f"SKU-{i % 7}")
                run_checked(gate, scanner, "read", [], claim=claim, audit=audit)
            elif kind == "lights":
                claim = claim_from_ticket_claims(
                    {
                        "room": "party",
                        "peer_id": f"g{i}",
                        "scopes": ["lights"],
                        "exp": time.time() + 30,
                    }
                )
                run_checked(
                    gate,
                    lights,
                    "scene",
                    [random.choice(["party", "dim", "off"])],
                    claim=claim,
                    audit=audit,
                )
            elif kind == "flash":
                claim = claim_from_ticket_claims(
                    {
                        "room": "lab",
                        "peer_id": f"t{i}",
                        "scopes": ["lab", "lab.flash"],
                    }
                )
                q = Quantity.from_store(
                    1, "count", source="lab.budget", revision=i
                )
                run_checked(
                    gate, lab, "flash", [], claim=claim, quantity=q, audit=audit
                )
            else:
                claim = claim_from_ticket_claims(
                    {"room": "party", "peer_id": "x", "scopes": ["lights"]}
                )
                run_checked(gate, lab, "flash", [], claim=claim, audit=audit)
            n_ok += 1
        except (IoChannelError, ValueError):
            n_fail += 1
    dt = time.time() - t0
    print(
        f"soak ok={n_ok} fail={n_fail} audit={len(audit.export())} "
        f"dt={dt:.3f}s flashes={lab.flash_count}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
