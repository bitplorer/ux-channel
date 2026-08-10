#!/usr/bin/env python3
"""Real-world CXB benchmarks — realistic Intent/Result shapes from day-1 apps.

Usage::

    PYTHONPATH=src python scripts/bench_cxb_realworld.py
    PYTHONPATH=src python scripts/bench_cxb_realworld.py --write docs/core/CXB_REALWORLD.md
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from pathlib import Path
from typing import Any, Callable

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ux_channel.protocol import ops as O  # noqa: E402
from ux_channel.wire import encode as wire_encode  # noqa: E402
from ux_channel.wire.cxb import decode_cxb, encode_cxb  # noqa: E402


def _time_us(fn: Callable[[], Any], n: int = 200, warmup: int = 30) -> dict[str, float]:
    for _ in range(warmup):
        fn()
    samples: list[float] = []
    for _ in range(n):
        t0 = time.perf_counter()
        fn()
        samples.append((time.perf_counter() - t0) * 1e6)
    samples.sort()
    return {
        "mean": round(statistics.mean(samples), 1),
        "p50": round(samples[len(samples) // 2], 1),
        "p95": round(samples[int(n * 0.95)], 1),
        "min": round(samples[0], 1),
        "max": round(samples[-1], 1),
    }


def fixtures() -> dict[str, dict[str, Any]]:
    """Real app-shaped documents (not synthetic micro-payloads only)."""
    cart_html = (
        '<div data-channel-id="cart">'
        + "".join(f'<li data-sku="sku-{i}">Item {i} × {i+1}</li>' for i in range(12))
        + "</div>"
    )
    form_html = (
        '<form data-channel-id="signup">'
        '<input name="email" value="user@example.com"/>'
        '<ul class="errors"><li>Password too short</li></ul>'
        "</form>"
    )
    dash_html = (
        '<section data-channel-id="dashboard">'
        + "".join(f'<article class="card"><h3>M{i}</h3><p>{"stat " * 8}</p></article>' for i in range(8))
        + "</section>"
    )

    return {
        "intent_cart_add": {
            "v": "1",
            "action": "Cart.add",
            "args": {"sku": "SKU-42", "qty": 2, "opts": {"color": "navy"}},
            "cap": "x" * 48,
            "request_id": "req_cart_01",
            "target": '[data-channel-id="cart"]',
            "meta": {"csrf": "tok", "path": "/shop"},
        },
        "result_cart_toast_morph": {
            "v": "1",
            "ok": True,
            "ops": [
                O.toast("Added to cart", level="success", duration_ms=2500),
                O.morph('[data-channel-id="cart"]', cart_html),
                O.signal_set("cart.count", 12),
                O.dispatch("cart:changed", target="#app", detail={"count": 12}),
            ],
            "meta": {"action": "Cart.add", "request_id": "req_cart_01"},
        },
        "result_login_fail": {
            "v": "1",
            "ok": False,
            "ops": [
                O.clear_errors('[data-channel-id="login"]'),
                O.set_attr("#email", {"aria-invalid": "true"}),
                O.focus("#password", select=True),
                O.toast("Invalid credentials", level="error"),
            ],
            "error": {
                "code": "unauthorized",
                "message": "Invalid credentials",
                "fields": {"email": ["unknown user"], "password": ["mismatch"]},
                "retryable": False,
            },
            "meta": {"action": "Auth.login"},
        },
        "result_signup_validation": {
            "v": "1",
            "ok": False,
            "ops": [
                O.morph('[data-channel-id="signup"]', form_html),
                O.toast("Please fix the form", level="warning"),
            ],
            "error": {
                "code": "validation",
                "message": "Form invalid",
                "fields": {"password": ["too short"], "email": []},
                "retryable": True,
            },
            "meta": {"action": "Auth.signup"},
        },
        "result_dashboard_refresh": {
            "v": "1",
            "ok": True,
            "ops": [
                O.morph('[data-channel-id="dashboard"]', dash_html),
                O.toast("Dashboard updated", level="info"),
                O.bridge_update("chart-main", {"series": [1, 4, 9, 16, 25]}, replace=True),
                O.scroll(target="#main", top=0, behavior="smooth"),
            ],
            "meta": {"action": "Dash.refresh", "request_id": "req_d1"},
        },
        "result_multi_region_morph": {
            "v": "1",
            "ok": True,
            "ops": [
                O.morph(f'[data-channel-id="r{i}"]', f'<span data-channel-id="r{i}">n={i}</span>')
                for i in range(10)
            ]
            + [O.toast("Regions synced", level="success")],
            "meta": {"action": "Region.sync"},
        },
        "result_nav_after_save": {
            "v": "1",
            "ok": True,
            "ops": [
                O.toast("Saved", level="success"),
                O.push_url("/orders/99"),
                O.navigate("/orders/99"),
            ],
            "meta": {"action": "Order.save"},
        },
        "result_bridge_lifecycle": {
            "v": "1",
            "ok": True,
            "ops": [
                O.bridge_mount("map-1", "leaflet", props={"lat": 26.85, "lng": 80.95}, target="#map"),
                O.bridge_call("map-1", "flyTo", args=[26.85, 80.95, 14]),
                O.bridge_update("map-1", {"zoom": 14}),
                O.bridge_destroy("map-1"),
            ],
            "meta": {"action": "Map.cycle"},
        },
        "result_bulk_toasts": {
            "v": "1",
            "ok": True,
            "ops": [O.toast("Saved", level="success")] * 40,
            "meta": {"action": "Bulk.noop"},
        },
        "intent_search": {
            "v": "1",
            "action": "Search.query",
            "args": {
                "q": "navy linen shirt",
                "filters": {"size": ["M", "L"], "on_sale": True},
                "page": 1,
            },
            "cap": "y" * 48,
            "request_id": "req_search",
        },
    }


def run(rounds: int = 200) -> dict[str, Any]:
    cases = fixtures()
    formats = ["json", "msgpack", "cxb"]
    out: dict[str, Any] = {"rounds": rounds, "cases": {}}

    for name, doc in cases.items():
        # correctness first
        back = decode_cxb(encode_cxb(doc))
        # structural checks
        assert back.get("v") == doc.get("v") or "v" not in doc
        if "ops" in doc:
            assert len(back["ops"]) == len(doc["ops"])
            for a, b in zip(doc["ops"], back["ops"]):
                assert a.get("op") == b.get("op")

        sizes = {}
        for fmt in formats:
            try:
                sizes[fmt] = len(wire_encode(doc, format=fmt).data)
            except Exception as exc:  # noqa: BLE001
                sizes[fmt] = f"err:{exc}"

        enc = _time_us(lambda d=doc: encode_cxb(d), rounds)
        raw = encode_cxb(doc)
        dec = _time_us(lambda r=raw: decode_cxb(r), rounds)
        rt = _time_us(lambda d=doc: decode_cxb(encode_cxb(d)), rounds)

        j = sizes.get("json") or 1
        if isinstance(j, int) and j > 0 and isinstance(sizes.get("cxb"), int):
            density = round(j / sizes["cxb"], 2)
        else:
            density = None

        out["cases"][name] = {
            "sizes": sizes,
            "density_vs_json": density,
            "encode_us": enc,
            "decode_us": dec,
            "roundtrip_us": rt,
            "magic": raw[:4].decode("ascii", errors="replace"),
            "ops": len(doc.get("ops") or []),
        }
    return out


def to_markdown(results: dict[str, Any]) -> str:
    lines = [
        "# CXB real-world benchmarks",
        "",
        "Fixtures mirror production channel shapes (cart, auth, dashboard, bridges).",
        f"Rounds per timing cell: **{results['rounds']}**.",
        "",
        "## Size (bytes) & density",
        "",
        "| Case | ops | JSON | msgpack | CXB | magic | vs JSON |",
        "|------|----:|-----:|--------:|----:|-------|--------:|",
    ]
    for name, c in results["cases"].items():
        s = c["sizes"]
        lines.append(
            f"| {name} | {c['ops']} | {s.get('json')} | {s.get('msgpack')} | "
            f"{s.get('cxb')} | {c['magic']} | {c['density_vs_json'] or '—'}× |"
        )
    lines += [
        "",
        "## Latency (µs) — encode / decode / round-trip",
        "",
        "| Case | enc mean | enc p95 | dec mean | dec p95 | rt mean | rt p95 |",
        "|------|---------:|--------:|---------:|--------:|--------:|-------:|",
    ]
    for name, c in results["cases"].items():
        e, d, r = c["encode_us"], c["decode_us"], c["roundtrip_us"]
        lines.append(
            f"| {name} | {e['mean']} | {e['p95']} | {d['mean']} | {d['p95']} | "
            f"{r['mean']} | {r['p95']} |"
        )
    lines += [
        "",
        "## Reading",
        "",
        "- **Cart / multi-region / bulk toasts** — CXB density shines (intern + tags + CXBZ).",
        "- **Single intent** — smaller absolute sizes; JSON+orjson still fine for browsers.",
        "- Latency is pure-Python CXB; network/RTT usually dominates over encode µs.",
        "",
        "```bash",
        "PYTHONPATH=src python scripts/bench_cxb_realworld.py --write docs/core/CXB_REALWORLD.md",
        "```",
        "",
    ]
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--rounds", type=int, default=200)
    ap.add_argument("--write", type=Path, default=None)
    ap.add_argument("--json", type=Path, default=None)
    args = ap.parse_args()
    results = run(rounds=args.rounds)
    md = to_markdown(results)
    print(md)
    if args.write:
        args.write.parent.mkdir(parents=True, exist_ok=True)
        args.write.write_text(md)
        print(f"wrote {args.write}", file=sys.stderr)
    if args.json:
        args.json.write_text(json.dumps(results, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
