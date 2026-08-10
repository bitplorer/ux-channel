"""SLO aggregation + report rendering."""

from __future__ import annotations

import json
import statistics
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any


@dataclass
class ScenarioResult:
    name: str
    ok: bool
    detail: dict[str, Any] = field(default_factory=dict)
    error: str | None = None


@dataclass
class SloConfig:
    action_success: float = 0.99
    rtc_success: float = 0.99
    ticket_deny: float = 1.0  # fraction of unauthed that must be denied
    p95_rtc_ms: float = 200.0
    p95_action_ms: float = 100.0
    ws_hello: float = 0.98

    @classmethod
    def for_mode(cls, mode: str) -> "SloConfig":
        if mode == "http":
            return cls(p95_rtc_ms=500.0, p95_action_ms=300.0)
        return cls()


def p95(values: list[float]) -> float:
    if not values:
        return 0.0
    xs = sorted(values)
    idx = max(0, int(round(0.95 * (len(xs) - 1))))
    return float(xs[idx])


def rate(ok: int, total: int) -> float:
    if total <= 0:
        return 0.0
    return ok / total


@dataclass
class SoakReport:
    mode: str
    started_at: float
    finished_at: float = 0.0
    scenarios: list[ScenarioResult] = field(default_factory=list)
    metrics_end: dict[str, Any] = field(default_factory=dict)
    slo: dict[str, Any] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return all(s.ok for s in self.scenarios) and bool(self.scenarios)

    @property
    def duration_s(self) -> float:
        end = self.finished_at or time.time()
        return round(end - self.started_at, 3)

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "mode": self.mode,
            "duration_s": self.duration_s,
            "slo": self.slo,
            "scenarios": [
                {
                    "name": s.name,
                    "ok": s.ok,
                    "error": s.error,
                    "detail": s.detail,
                }
                for s in self.scenarios
            ],
            "metrics_end": self.metrics_end,
        }

    def write(self, path: str | Path) -> None:
        Path(path).write_text(json.dumps(self.to_dict(), indent=2), encoding="utf-8")

    def text(self) -> str:
        lines = [
            f"soak report  mode={self.mode}  duration={self.duration_s}s  "
            f"{'PASS' if self.ok else 'FAIL'}",
            "-" * 60,
        ]
        for s in self.scenarios:
            mark = "OK " if s.ok else "ERR"
            lines.append(f"  [{mark}] {s.name}: {s.detail or s.error or ''}")
        if self.metrics_end:
            ctr = (self.metrics_end.get("counters") or {})
            lines.append(
                f"  metrics signals_total={ctr.get('signals_total', 0)} "
                f"poll_total={ctr.get('poll_total', 0)} "
                f"auth_fail={ctr.get('auth_fail', 0)}"
            )
        return "\n".join(lines)
