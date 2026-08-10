"""Logging and metrics hooks for production observability.

Heavy-lifting apps need to answer: which actions are slow, failing, or hot?
Channel must not force OpenTelemetry, but must make instrumentation trivial.

- Structured log records via stdlib logging
- Metrics protocol (counters/timers) apps can bind to Prometheus/StatsD
- after-hook factory used by ActionRegistry.from_config

::

   …"""

from __future__ import annotations

from ux_channel.protocol import serde as _serde

import logging
import time
from typing import Any, Callable, Optional, Protocol

from ux_channel.protocol.types import Intent, Result

logger = logging.getLogger("ux_channel.actions")


class Metrics(Protocol):
    """Minimal metrics sink — implement with Prometheus, Datadog, etc."""

    def incr(self, name: str, value: float = 1.0, **tags: str) -> None: ...
    def timing(self, name: str, ms: float, **tags: str) -> None: ...


class NullMetrics:
    """No-op metrics (default)."""

    def incr(self, name: str, value: float = 1.0, **tags: str) -> None:
        return None

    def timing(self, name: str, ms: float, **tags: str) -> None:
        return None


class InMemoryMetrics:
    """
    Simple process-local metrics for tests and single-node dashboards.

    Not for multi-worker aggregation — export elsewhere in real prod.
    """

    def __init__(self) -> None:
        self.counters: dict[str, float] = {}
        self.timings: dict[str, list[float]] = {}

    def incr(self, name: str, value: float = 1.0, **tags: str) -> None:
        key = name + _tag_suffix(tags)
        self.counters[key] = self.counters.get(key, 0.0) + value

    def timing(self, name: str, ms: float, **tags: str) -> None:
        key = name + _tag_suffix(tags)
        self.timings.setdefault(key, []).append(ms)


def _tag_suffix(tags: dict[str, str]) -> str:
    if not tags:
        return ""
    parts = ",".join(f"{k}={v}" for k, v in sorted(tags.items()))
    return "{" + parts + "}"


def observability_after_hook(
    *,
    metrics: Optional[Metrics] = None,
    log_slow_ms: float = 200.0,
    log_all: bool = False,
    json_logs: bool = False,
) -> Callable[[Intent, Result], Result]:
    """
    After-hook: metrics + structured logs for every action Result.

    Logs at INFO when slow or failed; DEBUG when log_all=True.
    Set ``json_logs=True`` for one JSON object per line (automation).
    """
    import json as _json
    import time as _time

    m: Metrics = metrics or NullMetrics()

    def _emit(level: int, event: str, **fields: Any) -> None:
        if json_logs:
            rec = {
                "ts": _time.time(),
                "level": logging.getLevelName(level).lower(),
                "event": event,
                "logger": "ux_channel.actions",
                **fields,
            }
            logger.log(level, _serde.dumps(rec, default=str))
        else:
            # keep key=value message for grepping
            kv = " ".join(f"{k}={v}" for k, v in fields.items())
            logger.log(level, "%s %s", event, kv)

    def hook(intent: Intent, result: Result) -> Result:
        action = intent.action
        ms = float(result.meta.get("duration_ms") or 0.0)
        ok = "true" if result.ok else "false"
        m.incr("ux_channel.actions", action=str(action), ok=str(ok))
        m.timing("ux_channel.action_ms", ms, action=action, ok=ok)
        base = {
            "action": action,
            "duration_ms": round(ms, 3),
            "request_id": intent.request_id,
            "ok": result.ok,
        }
        if not result.ok:
            code = result.error.code if result.error else "unknown"
            m.incr("ux_channel.action_errors", action=str(action), code=str(code))
            _emit(logging.WARNING, "action_failed", code=code, **base)
        elif ms >= log_slow_ms:
            _emit(logging.INFO, "action_slow", **base)
        elif log_all:
            _emit(logging.DEBUG, "action_ok", **base)
        return result

    return hook
