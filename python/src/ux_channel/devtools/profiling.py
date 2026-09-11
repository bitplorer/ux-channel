# Copyright (c) 2026 UX-CHANNEL
"""Internal / maintainer profiling helpers (not a application user API).

Dispatch parallelism, bulkheads, and batch concurrency are **library-internal**
defaults for safety under load. Applications should not need to tune them.
"""

from __future__ import annotations

# Re-implement thin copies to avoid cross-package import of ux_dom.
import cProfile
import io
import json
import pstats
import statistics
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Callable, Optional, Sequence


@dataclass
class LatencyReport:
    name: str
    n: int
    p50_ms: float
    p95_ms: float
    p99_ms: float
    mean_ms: float
    min_ms: float
    max_ms: float
    samples_ms: list[float] = field(default_factory=list, repr=False)

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d.pop("samples_ms", None)
        return d


def _percentile(sorted_vals: Sequence[float], p: float) -> float:
    if not sorted_vals:
        return 0.0
    if len(sorted_vals) == 1:
        return float(sorted_vals[0])
    k = (len(sorted_vals) - 1) * (p / 100.0)
    f = int(k)
    c = min(f + 1, len(sorted_vals) - 1)
    if f == c:
        return float(sorted_vals[f])
    return float(sorted_vals[f] + (sorted_vals[c] - sorted_vals[f]) * (k - f))


def measure_latency(
    fn: Callable[[], Any],
    *,
    name: str = "op",
    rounds: int = 100,
    warmup: int = 10,
) -> LatencyReport:
    for _ in range(max(0, warmup)):
        fn()
    samples: list[float] = []
    for _ in range(rounds):
        t0 = time.perf_counter()
        fn()
        samples.append((time.perf_counter() - t0) * 1000.0)
    samples.sort()
    return LatencyReport(
        name=name,
        n=len(samples),
        p50_ms=round(_percentile(samples, 50), 4),
        p95_ms=round(_percentile(samples, 95), 4),
        p99_ms=round(_percentile(samples, 99), 4),
        mean_ms=round(statistics.fmean(samples), 4) if samples else 0.0,
        min_ms=round(samples[0], 4) if samples else 0.0,
        max_ms=round(samples[-1], 4) if samples else 0.0,
        samples_ms=samples,
    )


def profile_cprofile(
    fn: Callable[[], Any],
    *,
    name: str = "op",
    rounds: int = 50,
) -> tuple[pstats.Stats, str]:
    pr = cProfile.Profile()
    pr.enable()
    for _ in range(rounds):
        fn()
    pr.disable()
    buf = io.StringIO()
    st = pstats.Stats(pr, stream=buf).sort_stats(pstats.SortKey.CUMULATIVE)
    st.print_stats(40)
    return st, buf.getvalue()


def cprofile_to_speedscope(stats: pstats.Stats, *, name: str = "ux-channel") -> dict[str, Any]:
    frames: dict[tuple, int] = {}
    frame_list: list[dict[str, Any]] = []

    def frame_id(key: tuple) -> int:
        if key not in frames:
            frames[key] = len(frame_list)
            filename, line, func = key
            frame_list.append(
                {
                    "name": f"{func}",
                    "file": str(filename),
                    "line": int(line) if line else 0,
                    "col": 0,
                }
            )
        return frames[key]

    samples: list[int] = []
    weights: list[int] = []
    for func, (_cc, _nc, _tt, ct, _callers) in stats.stats.items():  # type: ignore[attr-defined]
        fid = frame_id(func)
        w = max(1, int(ct * 1_000_000))
        samples.append(fid)
        weights.append(w)

    return {
        "$schema": "https://www.speedscope.app/file-format-schema.json",
        "shared": {"frames": frame_list},
        "profiles": [
            {
                "type": "sampled",
                "name": name,
                "unit": "microseconds",
                "startValue": 0,
                "endValue": sum(weights) if weights else 0,
                "samples": [[s] for s in samples],
                "weights": weights,
            }
        ],
        "name": name,
        "activeProfileIndex": 0,
        "exporter": "ux_channel.devtools.profiling",
    }


def write_html_report(path, *, title, latencies, pstats_text="", notes=""):
    # import twin implementation via copy of structure — keep dependency-free
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = "".join(
        f"<tr><td>{r.name}</td><td>{r.n}</td><td>{r.p50_ms}</td>"
        f"<td><b>{r.p95_ms}</b></td><td>{r.p99_ms}</td>"
        f"<td>{r.mean_ms}</td><td>{r.min_ms}</td><td>{r.max_ms}</td></tr>"
        for r in latencies
    )
    max_p95 = max((r.p95_ms for r in latencies), default=1.0) or 1.0
    bars = "".join(
        f'<div><span style="display:inline-block;width:14rem">{r.name}</span>'
        f'<span style="display:inline-block;background:#7c3aed;color:#fff;'
        f'padding:2px 8px;border-radius:4px;width:{max(2, int(80 * r.p95_ms / max_p95))}%">'
        f"p95 {r.p95_ms} ms</span></div>"
        for r in latencies
    )
    html = f"""<!DOCTYPE html><html><head><meta charset="utf-8"><title>{title}</title>
<style>body{{font-family:system-ui,sans-serif;margin:2rem}}
table{{border-collapse:collapse;width:100%}}
th,td{{border:1px solid #e2e8f0;padding:.4rem .6rem}}
th{{background:#f8fafc}}
pre{{background:#0f172a;color:#e2e8f0;padding:1rem;overflow:auto;font-size:.75rem}}
.note{{color:#64748b}}</style></head><body>
<h1>{title}</h1>
<p class="note">Users do not configure concurrency — bulkhead/parallel are internal.
Open <code>profile.speedscope.json</code> in speedscope.app for a flamegraph.</p>
<p class="note">{notes}</p>
<table><tr><th>name</th><th>n</th><th>p50</th><th>p95</th><th>p99</th>
<th>mean</th><th>min</th><th>max</th></tr>{rows}</table>
<h2>p95</h2>{bars}
<pre>{pstats_text.replace('<','<')}</pre></body></html>"""
    path.write_text(html, encoding="utf-8")
    return path


def run_suite(benches, *, out_dir, title, rounds=80, warmup=8, profile_rounds=40):
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    latencies = []

    def all_ops():
        for _n, fn in benches:
            fn()

    stats, text = profile_cprofile(all_ops, name=title, rounds=profile_rounds)
    for name, fn in benches:
        latencies.append(measure_latency(fn, name=name, rounds=rounds, warmup=warmup))
    report = {
        "title": title,
        "latencies": [r.to_dict() for r in latencies],
        "note": "Concurrency is internal; apps should not tune parallel flags.",
    }
    (out_dir / "latency.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    (out_dir / "cprofile.txt").write_text(text, encoding="utf-8")
    (out_dir / "profile.speedscope.json").write_text(
        json.dumps(cprofile_to_speedscope(stats, name=title)), encoding="utf-8"
    )
    write_html_report(
        out_dir / "report.html",
        title=title,
        latencies=latencies,
        pstats_text=text,
        notes="p95 is the primary SLI.",
    )
    return report


def cmd_profile(args: Any) -> int:
    """First-class DX: p95 latency + flamegraph for dispatch / batch."""
    from ux_channel.devtools.log import get_log
    from ux_channel.host.registry import ActionRegistry
    from ux_channel.protocol.types import Intent, Result
    from ux_channel.transport.batch import dispatch_batch
    from ux_channel.transport.concurrency import dispatch_parallel

    log = get_log()
    out = Path(args.out) if getattr(args, "out", None) else Path.cwd() / "reports" / "p95"
    rounds = int(getattr(args, "rounds", 50) or 50)
    warmup = int(getattr(args, "warmup", 5) or 5)
    profile_rounds = int(getattr(args, "profile_rounds", 25) or 25)

    reg = ActionRegistry(
        secret="test-secret-key-32chars-minimum!!!!",
        require_cap=False,
    )

    @reg.action("echo")
    def echo(ctx, n: int = 0):
        return Result.success(n=n)

    intents = [
        Intent(action="echo", args={"n": i}, request_id=f"r{i}") for i in range(32)
    ]
    items = [
        {"action": "echo", "args": {"n": i}, "request_id": f"b{i}"} for i in range(16)
    ]

    def one_dispatch():
        reg.dispatch(Intent(action="echo", args={"n": 1}, request_id="solo"))

    def parallel_dispatch():
        dispatch_parallel(reg, intents)

    def batch_dispatch():
        dispatch_batch(reg, items)

    report = run_suite(
        [
            ("dispatch_one", one_dispatch),
            ("dispatch_parallel_32", parallel_dispatch),
            ("dispatch_batch_16", batch_dispatch),
        ],
        out_dir=out,
        title="ux-channel p95 suite",
        rounds=rounds,
        warmup=warmup,
        profile_rounds=profile_rounds,
    )
    log.ok(
        "profile complete",
        out=str(out.resolve()),
        html=str((out / "report.html").resolve()),
        speedscope=str((out / "profile.speedscope.json").resolve()),
    )
    if getattr(args, "json_report", False) or getattr(args, "json", False):
        print(json.dumps(report, indent=2))
    else:
        print("uxchannel profile")
        print("=" * 40)
        print("Brand lines")
        print("  PyPI / pip : ux-channel")
        print("  import     : ux_channel")
        print("  CLI        : uxchannel")
        print("-" * 40)
        print("p95 latency (ms)")
        for lat in report.get("latencies") or []:
            print(
                f"  {lat['name']:<28} p50={lat['p50_ms']:<8} "
                f"p95={lat['p95_ms']:<8} p99={lat['p99_ms']}"
            )
        print("-" * 40)
        print(f"out: {out.resolve()}")
        print(f"  html:       {(out / 'report.html').resolve()}")
        print(f"  speedscope: {(out / 'profile.speedscope.json').resolve()}")
        print("Open profile.speedscope.json at https://www.speedscope.app")
        print("=" * 40)
        print("OK — profiling complete (app source untouched)")
    return 0
