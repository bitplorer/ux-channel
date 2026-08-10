"""Example extension — data only."""

from __future__ import annotations

from ux_channel.devtools.dashboard import Panel, Widget


class TeamOverview:
    id = "example.team"
    title = "Team"
    order = 15

    def contribute(self, ctx):
        series = list(ctx.latencies or [])
        p95s = [float(x.get("p95_ms") or 0) for x in series]
        worst = max(p95s) if p95s else 0.0
        return [
            Panel.as_table(
                "example.team.summary",
                "Team overview",
                [
                    ("benches", len(series)),
                    ("worst p95 (ms)", round(worst, 4)),
                    ("serde", (ctx.runtime or {}).get("serde")),
                    ("doctor ok", (ctx.doctor or {}).get("ok")),
                ],
                order=15,
            ),
            Widget(
                "example.team.badge",
                "Badge",
                props={
                    "benches": len(series),
                    "worst_p95_ms": round(worst, 4),
                    "label": "tracked",
                },
                body="{label}: {benches}  ·  worst p95 {worst_p95_ms} ms",
                order=16,
                span=2,
                css="""
                  .ux-dx-view[data-channel-dx-widget="example.team.badge"] {
                    display: inline-flex;
                    padding: 0.55rem 0.9rem;
                    border-radius: 999px;
                    background: #312e81;
                    color: #e0e7ff;
                  }
                """,
            ),
            Widget(
                "example.team.raw",
                "Props (auto view)",
                props={
                    "benches": len(series),
                    "worst_p95_ms": round(worst, 4),
                    "serde": (ctx.runtime or {}).get("serde"),
                },
                order=17,
            ),
        ]
