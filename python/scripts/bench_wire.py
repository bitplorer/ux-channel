#!/usr/bin/env python3
# Copyright (c) 2026 UX-CHANNEL
"""
Wire codec micro-benchmarks → stdout + optional markdown.

::

    PYTHONPATH=src python scripts/bench_wire.py
    PYTHONPATH=src python scripts/bench_wire.py --write docs/core/WIRE_BENCH.md
"""

from __future__ import annotations

import argparse
import json
import platform
import statistics
import sys
import time
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT / "src"))

from ux_channel.wire import available_engines, available_formats, encode, decode  # noqa: E402
from ux_channel.wire.cxb import encode_cxb, decode_cxb  # noqa: E402


def _docs() -> dict[str, dict]:
    toast = {"op": "toast", "message": "Saved", "level": "success"}
    morph = {
        "op": "morph",
        "target": '[data-channel-id="cart"]',
        "html": "<div data-channel-id=\"cart\"><span>3</span></div>",
        "morph": "idiomorph",
    }
    return {
        "small_result": {
            "v": "1",
            "ok": True,
            "ops": [toast],
            "meta": {"action": "X"},
        },
        "multi_op": {
            "v": "1",
            "ok": True,
            "ops": [toast] * 20 + [morph] * 5,
            "meta": {"action": "Cart.add", "request_id": "r1", "runtime": "0.1.0"},
        },
        "html_heavy": {
            "v": "1",
            "ok": True,
            "ops": [
                {
                    "op": "morph",
                    "target": '[data-channel-id="x"]',
                    "html": "<div>" + ("item " * 400) + "</div>",
                    "morph": "idiomorph",
                }
            ],
            "meta": {"action": "Render"},
        },
        "intent": {
            "v": "1",
            "action": "Cart.add",
            "args": {"sku": "sku-1", "n": 2},
            "cap": "c" * 32,
            "request_id": "rid",
        },
    }




def bench_cxbz_decode(rounds: int = 300) -> dict:
    """CXB1 vs CXBZ decode latency + optional Brotli comparison (not on wire)."""
    import zlib
    from ux_channel.wire.cxb import encode_cxb, decode_cxb, MAGIC_Z

    try:
        import brotli
        has_brotli = True
    except ImportError:
        has_brotli = False

    def plain_of(doc):
        raw = encode_cxb(doc)
        if raw[:4] == MAGIC_Z:
            return zlib.decompress(raw[4:])
        return raw

    docs = {
        "ops_30": {
            "v": "1", "ok": True,
            "ops": [{"op": "toast", "message": "Saved", "level": "success"}] * 30,
        },
        "html_2k_rep": {
            "v": "1", "ok": True,
            "ops": [{
                "op": "morph", "target": "#x",
                "html": "<div>" + ("item " * 500) + "</div>",
                "morph": "idiomorph",
            }],
        },
    }
    out = {"has_brotli": has_brotli, "cases": {}}
    for name, doc in docs.items():
        plain = plain_of(doc)
        zframe = MAGIC_Z + zlib.compress(plain, 6)
        auto = encode_cxb(doc)
        case = {
            "cxb1_bytes": len(plain),
            "cxbz_bytes": len(zframe),
            "auto_magic": auto[:4].decode(),
            "auto_bytes": len(auto),
            "decode_cxb1_us": _time_us(lambda: decode_cxb(plain), rounds),
            "decode_cxbz_us": _time_us(lambda: decode_cxb(zframe), rounds),
            "decode_auto_us": _time_us(lambda: decode_cxb(auto), rounds),
        }
        if has_brotli:
            b4 = brotli.compress(plain, quality=4)
            case["brotli4_bytes"] = len(b4) + 4
            case["decode_brotli4_us"] = _time_us(
                lambda: decode_cxb(brotli.decompress(b4)), rounds
            )
            case["compress_zlib6_us"] = _time_us(
                lambda: zlib.compress(plain, 6), rounds
            )
            case["compress_brotli4_us"] = _time_us(
                lambda: brotli.compress(plain, quality=4), rounds
            )
        out["cases"][name] = case
    return out


def _time_us(fn, n: int) -> dict:
    import statistics
    import time
    for _ in range(min(30, n)):
        fn()
    samples = []
    for _ in range(n):
        t0 = time.perf_counter()
        fn()
        samples.append((time.perf_counter() - t0) * 1e6)
    samples.sort()
    return {
        "mean": round(statistics.mean(samples), 1),
        "p50": round(samples[len(samples) // 2], 1),
        "p95": round(samples[int(len(samples) * 0.95)], 1),
    }

def _time_ms(fn, n: int) -> dict:
    # warmup
    for _ in range(min(20, n)):
        fn()
    samples = []
    for _ in range(n):
        t0 = time.perf_counter()
        fn()
        samples.append((time.perf_counter() - t0) * 1000.0)
    samples.sort()
    return {
        "n": n,
        "mean_ms": round(statistics.mean(samples), 4),
        "p50_ms": round(samples[len(samples) // 2], 4),
        "p95_ms": round(samples[int(len(samples) * 0.95)], 4),
        "min_ms": round(samples[0], 4),
        "max_ms": round(samples[-1], 4),
    }


def run_bench(rounds: int = 200) -> dict:
    docs = _docs()
    fmts = available_formats()
    results: dict = {
        "meta": {
            "python": platform.python_version(),
            "platform": platform.platform(),
            "formats": fmts,
            "json_engines": available_engines(),
            "rounds": rounds,
        },
        "size_bytes": {},
        "roundtrip_ms": {},
    }

    for name, doc in docs.items():
        results["size_bytes"][name] = {}
        results["roundtrip_ms"][name] = {}
        for fmt in fmts:
            blob = encode(doc, format=fmt)
            results["size_bytes"][name][fmt] = len(blob.data)

            def rt(doc=doc, fmt=fmt):
                b = encode(doc, format=fmt)
                decode(b.data, format=fmt)

            results["roundtrip_ms"][name][fmt] = _time_ms(rt, rounds)

    # density ratios vs json
    results["density_vs_json"] = {}
    for name in docs:
        j = results["size_bytes"][name].get("json") or 1
        results["density_vs_json"][name] = {
            fmt: round(j / max(1, sz), 2)
            for fmt, sz in results["size_bytes"][name].items()
        }
    results["cxbz_decode"] = bench_cxbz_decode(max(50, rounds))
    return results


def to_markdown(results: dict) -> str:
    m = results["meta"]
    lines = [
        "# Wire codec performance (measured)",
        "",
        "Generated by ``scripts/bench_wire.py``. Re-run to refresh numbers.",
        "",
        f"- Python: `{m['python']}`",
        f"- Platform: `{m['platform']}`",
        f"- Formats: {', '.join(m['formats'])}",
        f"- JSON engines: {', '.join(m['json_engines'])}",
        f"- Rounds per cell: **{m['rounds']}**",
        "",
        "## Encoded size (bytes)",
        "",
    ]
    # size table
    fmts = m["formats"]
    lines.append("| Document | " + " | ".join(fmts) + " |")
    lines.append("|----------|" + "|".join(["------"] * len(fmts)) + "|")
    for name, sizes in results["size_bytes"].items():
        row = [name] + [str(sizes.get(f, "—")) for f in fmts]
        lines.append("| " + " | ".join(row) + " |")
    lines += ["", "## Density vs JSON (higher = smaller payload)", ""]
    lines.append("| Document | " + " | ".join(fmts) + " |")
    lines.append("|----------|" + "|".join(["------"] * len(fmts)) + "|")
    for name, dens in results["density_vs_json"].items():
        row = [name] + [str(dens.get(f, "—")) for f in fmts]
        lines.append("| " + " | ".join(row) + " |")

    lines += ["", "## Round-trip latency (encode+decode)", ""]
    lines.append(
        "| Document | Format | mean ms | p50 | p95 | min | max |"
    )
    lines.append("|----------|--------|---------|-----|-----|-----|-----|")
    for name, by_fmt in results["roundtrip_ms"].items():
        for fmt, t in by_fmt.items():
            lines.append(
                f"| {name} | {fmt} | {t['mean_ms']} | {t['p50_ms']} | "
                f"{t['p95_ms']} | {t['min_ms']} | {t['max_ms']} |"
            )

    # CXBZ decode + brotli compare
    if "cxbz_decode" in results:
        lines += ["", "## CXBZ decode latency (µs)", ""]
        cd = results["cxbz_decode"]
        lines.append(f"Brotli available for comparison: **{cd.get('has_brotli')}** (not on wire — zlib only).")
        lines.append("")
        lines.append("| Case | CXB1 B | CXBZ B | auto | dec CXB1 | dec CXBZ | dec auto | brotli4 B | dec brotli4 | zlib compress | brotli4 compress |")
        lines.append("|------|--------|--------|------|----------|----------|----------|-----------|-------------|---------------|------------------|")
        for name, c in cd.get("cases", {}).items():
            b = c.get("brotli4_bytes", "—")
            db = c.get("decode_brotli4_us", {})
            cz = c.get("compress_zlib6_us", {})
            cb = c.get("compress_brotli4_us", {})
            lines.append(
                f"| {name} | {c['cxb1_bytes']} | {c['cxbz_bytes']} | {c['auto_magic']}/{c['auto_bytes']}B | "
                f"{c['decode_cxb1_us']['mean']} | {c['decode_cxbz_us']['mean']} | {c['decode_auto_us']['mean']} | "
                f"{b} | {db.get('mean', '—') if isinstance(db, dict) else '—'} | "
                f"{cz.get('mean', '—') if isinstance(cz, dict) else '—'} | "
                f"{cb.get('mean', '—') if isinstance(cb, dict) else '—'} |"
            )
        lines.append("")
        lines.append("Brotli is **not** a wire magic; comparison only. CXBZ stays zlib (stdlib, no extra dep).")

    lines += [
        "",
        "## Reading the numbers",
        "",
        "- **Browsers** stay on **JSON** (orjson when installed) — lowest JS friction.",
        "- **CXB** wins size on multi-op / repetitive HTML (intern + optional zlib).",
        "- **msgpack** is a solid generic binary; CXB is domain-specialized.",
        "- Pure-Python CXB is denser, not always faster; use it where bandwidth or",
        "  storage dominate. JSON+orjson wins raw µs for small docs.",
        "",
        "## Reproduce",
        "",
        "```bash",
        "PYTHONPATH=src python scripts/bench_wire.py --write docs/core/WIRE_BENCH.md",
        "```",
        "",
    ]
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--rounds", type=int, default=200)
    ap.add_argument("--write", type=Path, default=None)
    ap.add_argument("--json", type=Path, default=None)
    args = ap.parse_args(argv)
    results = run_bench(rounds=args.rounds)
    md = to_markdown(results)
    print(md)
    if args.write:
        args.write.parent.mkdir(parents=True, exist_ok=True)
        args.write.write_text(md, encoding="utf-8")
        print(f"wrote {args.write}", file=sys.stderr)
    if args.json:
        args.json.write_text(json.dumps(results, indent=2), encoding="utf-8")
        print(f"wrote {args.json}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
