"""
Agent audit log — every tool call is attributable in production.
"""

from __future__ import annotations

import json
import logging
import threading
import time
from dataclasses import asdict, dataclass, field
from typing import Any, Callable, List, Optional, Protocol

logger = logging.getLogger("ux_channel.agent_runtime.tool_audit")


@dataclass
class AuditEvent:
    ts: float
    session_id: str
    agent_id: str
    action: str
    ok: bool
    duration_ms: float
    request_id: Optional[str] = None
    error_code: Optional[str] = None
    dry_run: bool = False
    confirmed: bool = False
    args_preview: dict[str, Any] = field(default_factory=dict)
    meta: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class AuditSink(Protocol):
    def write(self, event: AuditEvent) -> None: ...


class LoggingAuditSink:
    """Structured log lines (ship to your log stack)."""

    def write(self, event: AuditEvent) -> None:
        logger.info(
            "agent_audit session=%s agent=%s action=%s ok=%s duration_ms=%.2f err=%s dry_run=%s",
            event.session_id,
            event.agent_id,
            event.action,
            event.ok,
            event.duration_ms,
            event.error_code,
            event.dry_run,
        )


class MemoryAuditSink:
    """In-process ring buffer for tests / inspector."""

    def __init__(self, retain: int = 1000):
        self._events: List[AuditEvent] = []
        self.retain = retain
        self._lock = threading.Lock()

    def write(self, event: AuditEvent) -> None:
        with self._lock:
            self._events.append(event)
            if len(self._events) > self.retain:
                self._events = self._events[-self.retain :]

    def events(self) -> list[AuditEvent]:
        with self._lock:
            return list(self._events)

    def clear(self) -> None:
        with self._lock:
            self._events.clear()


class MultiAuditSink:
    def __init__(self, *sinks: AuditSink):
        self.sinks = sinks

    def write(self, event: AuditEvent) -> None:
        for s in self.sinks:
            try:
                s.write(event)
            except Exception:
                logger.exception("audit sink failed")


def redact_args(args: dict[str, Any], keys: tuple[str, ...] = ("password", "token", "secret", "api_key")) -> dict[str, Any]:
    out = {}
    for k, v in list(args.items())[:50]:
        if any(x in k.lower() for x in keys):
            out[k] = "***"
        elif isinstance(v, (str, int, float, bool)) or v is None:
            out[k] = v if not isinstance(v, str) or len(v) < 200 else v[:200] + "…"  # type: ignore[assignment]
        else:
            out[k] = type(v).__name__
    return out
