#!/usr/bin/env python3
"""Execute SPEC/architecture inventory vectors against the production host kernel.

Requires PYTHONPATH to include python/src (verify.sh sets this).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VECTORS = ROOT / "vectors" / "arch"

from ux_channel.arch.drivers import make_web_drivers
from ux_channel.arch.effects import Node, graph
from ux_channel.arch.peer import PeerApply
from ux_channel.arch.project import project


def load_node(d: dict) -> Node:
    children = [load_node(c) for c in d.get("children") or []]
    return Node(kind=d["kind"], data=dict(d.get("data") or {}), children=children)


def run_project(doc: dict) -> list[str]:
    g = graph(*(load_node(n) for n in doc["nodes"]))
    ops = project(g, doc.get("hello") or {}, effects=doc.get("effects") or "auto")
    if ops != doc["expect_ops"]:
        return [f"{doc['id']}: ops {ops!r} != {doc['expect_ops']!r}"]
    return []


def run_apply(doc: dict) -> list[str]:
    peer = PeerApply(make_web_drivers(), max_nodes=int(doc.get("max_nodes") or 256))
    peer.apply_result({"ok": True, "ops": doc.get("ops") or [], "meta": doc.get("meta") or {}})
    errs = []
    if "expect_log" in doc and list(peer.ctx.get("log") or []) != [tuple(x) if isinstance(x, list) else x for x in doc["expect_log"]]:
        # log entries are tuples
        got = [list(x) if isinstance(x, tuple) else x for x in peer.ctx.get("log") or []]
        if got != doc["expect_log"]:
            errs.append(f"{doc['id']}: log {got!r} != {doc['expect_log']!r}")
    if "expect_reject" in doc and peer.ctx.get("reject") != doc["expect_reject"]:
        errs.append(f"{doc['id']}: reject {peer.ctx.get('reject')!r} != {doc['expect_reject']!r}")
    return errs


def main() -> int:
    if not VECTORS.is_dir():
        print("arch vectors missing", file=sys.stderr)
        return 2
    errors: list[str] = []
    n = 0
    for path in sorted(VECTORS.glob("*.json")):
        doc = json.loads(path.read_text(encoding="utf-8"))
        kind = doc.get("kind")
        n += 1
        if kind == "project":
            errors.extend(run_project(doc))
        elif kind in ("apply", "budget"):
            errors.extend(run_apply(doc))
        else:
            errors.append(f"{path.name}: unknown kind {kind}")
    if errors:
        for e in errors:
            print("FAIL", e, file=sys.stderr)
        return 1
    print(f"arch vectors ok ({n})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
