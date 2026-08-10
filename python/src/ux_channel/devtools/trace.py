"""Action & bridge tracing — Wireshark-like Developer tooling for the Channel protocol.
When server-driven UI misbehaves, you need a **packet capture** of:
  Intent → cap verify → hooks → handler → encode → Result.ops
  (and on the client) apply each op + bridge mount/update/call
This module records ordered **frames** (like PCAP packets) in a ring buffer,
correlates them by ``request_id`` /…"""

from __future__ import annotations

from ux_channel.protocol import serde as _serde

import json
import threading
import time
import uuid
from collections import deque
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Callable, Deque, Iterator, Optional, Sequence


class FrameKind(str, Enum):
    """Frame types — analogous to protocol layers in a capture."""

    INTENT_IN = "intent.in"
    CAP_OK = "cap.ok"
    CAP_FAIL = "cap.fail"
    HOOK_BEFORE = "hook.before"
    HOOK_SHORT = "hook.short_circuit"
    HANDLER_START = "handler.start"
    HANDLER_END = "handler.end"
    HANDLER_ERROR = "handler.error"
    ENCODE = "encode"
    RESULT_OUT = "result.out"
    OP = "op"  # individual apply op summary
    BRIDGE = "bridge"  # server-emitted bridge op detail
    LIMIT = "limit"
    HTTP = "http"
    RATE_LIMIT = "rate_limit"
    CUSTOM = "custom"


@dataclass
class TraceFrame:
    """
    One capture frame (one \"packet\" in the Channel conversation).

    Fields mirror what you'd want in Wireshark columns: time, stream id,
    direction-ish kind, summary, optional full payload.
    """

    seq: int
    ts: float  # time.time()
    kind: str
    summary: str
    request_id: Optional[str] = None
    trace_id: Optional[str] = None
    action: Optional[str] = None
    duration_ms: Optional[float] = None
    ok: Optional[bool] = None
    detail: dict[str, Any] = field(default_factory=dict)

    def to_dict(self, *, include_detail: bool = True) -> dict[str, Any]:
        d: dict[str, Any] = {
            "seq": self.seq,
            "ts": self.ts,
            "kind": self.kind,
            "summary": self.summary,
        }
        if self.request_id:
            d["request_id"] = self.request_id
        if self.trace_id:
            d["trace_id"] = self.trace_id
        if self.action:
            d["action"] = self.action
        if self.duration_ms is not None:
            d["duration_ms"] = self.duration_ms
        if self.ok is not None:
            d["ok"] = self.ok
        if include_detail and self.detail:
            d["detail"] = self.detail
        return d


@dataclass
class TraceConfig:
    """Tracer knobs — keep disabled in public production unless debugging."""

    enabled: bool = False
    retain: int = 500  # ring buffer size
    # Capture full Intent args / Result ops (may contain PII — dev only)
    capture_payloads: bool = True
    max_detail_bytes: int = 32_000
    # Redact keys whose names look sensitive
    sample_rate: float = 1.0  # 0.0–1.0 production sampling
    redact_keys: tuple[str, ...] = (
        "password",
        "token",
        "secret",
        "authorization",
        "cap",
        "cookie",
    )


class ChannelTracer:
    """
    Process-local ring buffer of TraceFrames + subscriber callbacks.

    Thread-safe for threaded servers. Not multi-process (each worker has its own).
    """

    def __init__(self, config: Optional[TraceConfig] = None):
        self._config = config or TraceConfig()
        self._frames: Deque[TraceFrame] = deque(maxlen=self._config.retain)
        self._seq = 0
        self._lock = threading.Lock()
        self._subscribers: list[Callable[[TraceFrame], None]] = []

    def configure(self, config: TraceConfig) -> None:
        with self._lock:
            self._config = config
            # resize ring
            old = list(self._frames)
            self._frames = deque(old[-config.retain :], maxlen=config.retain)

    @property
    def enabled(self) -> bool:
        return self._config.enabled

    @property
    def config(self) -> TraceConfig:
        return self._config

    def subscribe(self, fn: Callable[[TraceFrame], None]) -> Callable[[TraceFrame], None]:
        """Live tail callback (e.g. SSE push)."""
        self._subscribers.append(fn)
        return fn

    def unsubscribe(self, fn: Callable[[TraceFrame], None]) -> None:
        self._subscribers = [s for s in self._subscribers if s is not fn]

    def clear(self) -> None:
        with self._lock:
            self._frames.clear()

    def emit(
        self,
        kind: str | FrameKind,
        summary: str,
        *,
        request_id: Optional[str] = None,
        trace_id: Optional[str] = None,
        action: Optional[str] = None,
        duration_ms: Optional[float] = None,
        ok: Optional[bool] = None,
        detail: Optional[dict[str, Any]] = None,
    ) -> Optional[TraceFrame]:
        if not self._config.enabled:
            return None
        # sampling: always keep failures; otherwise sample_rate
        if ok is not False and self._config.sample_rate < 1.0:
            import random
            if random.random() > self._config.sample_rate:
                return None
        kind_s = kind.value if isinstance(kind, FrameKind) else str(kind)
        det = self._prepare_detail(detail or {})
        with self._lock:
            self._seq += 1
            frame = TraceFrame(
                seq=self._seq,
                ts=time.time(),
                kind=kind_s,
                summary=summary,
                request_id=request_id,
                trace_id=trace_id,
                action=action,
                duration_ms=duration_ms,
                ok=ok,
                detail=det,
            )
            self._frames.append(frame)
        for sub in list(self._subscribers):
            try:
                sub(frame)
            except Exception:
                import logging

                logging.getLogger("ux_channel.devtools.trace").debug(
                    "trace subscriber failed", exc_info=True
                )
        return frame

    def _prepare_detail(self, detail: dict[str, Any]) -> dict[str, Any]:
        if not self._config.capture_payloads:
            return {"_payloads": "disabled"}
        redacted = _redact(detail, self._config.redact_keys)
        try:
            raw = _serde.dumps(redacted, default=str)
        except Exception:
            return {"_error": "detail_not_serializable"}
        if len(raw.encode("utf-8")) > self._config.max_detail_bytes:
            return {
                "_truncated": True,
                "_bytes": len(raw.encode("utf-8")),
                "preview": raw[:1000],
            }
        return redacted

    def frames(
        self,
        *,
        request_id: Optional[str] = None,
        action: Optional[str] = None,
        kind_prefix: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> list[TraceFrame]:
        with self._lock:
            items = list(self._frames)
        if request_id:
            items = [f for f in items if f.request_id == request_id]
        if action:
            items = [f for f in items if f.action == action]
        if kind_prefix:
            items = [f for f in items if f.kind.startswith(kind_prefix)]
        if limit is not None:
            items = items[-limit:]
        return items

    def conversations(self) -> list[dict[str, Any]]:
        """
        Group frames by request_id into conversation summaries (Wireshark streams).
        """
        by: dict[str, list[TraceFrame]] = {}
        with self._lock:
            items = list(self._frames)
        for f in items:
            key = f.request_id or f"anon-{f.seq}"
            by.setdefault(key, []).append(f)
        out = []
        for rid, frs in by.items():
            actions = [f.action for f in frs if f.action]
            result_frames = [f for f in frs if f.kind == FrameKind.RESULT_OUT.value]
            ok = result_frames[-1].ok if result_frames else None
            duration = None
            if result_frames and result_frames[-1].duration_ms is not None:
                duration = result_frames[-1].duration_ms
            out.append(
                {
                    "request_id": rid,
                    "action": actions[-1] if actions else None,
                    "frames": len(frs),
                    "ok": ok,
                    "duration_ms": duration,
                    "kinds": [f.kind for f in frs],
                    "first_ts": frs[0].ts,
                    "last_ts": frs[-1].ts,
                }
            )
        out.sort(key=lambda x: x["last_ts"], reverse=True)  # type: ignore[arg-type, return-value]
        return out

    def export_json(self, *, include_detail: bool = True) -> str:
        with self._lock:
            frames = [f.to_dict(include_detail=include_detail) for f in self._frames]
        return _serde.dumps(
            {
                "uid_trace": "1",
                "enabled": self._config.enabled,
                "count": len(frames),
                "frames": frames,
                "conversations": self.conversations(),
            },
            indent=2,
            default=str,
        )

    def record_result_ops(
        self,
        result: Any,
        *,
        request_id: Optional[str],
        action: Optional[str],
        trace_id: Optional[str] = None,
    ) -> None:
        """Expand Result.ops into per-op frames (document vs bridge planes)."""
        if not self._config.enabled:
            return
        ops = getattr(result, "ops", None) or []
        for i, op in enumerate(ops):
            if not isinstance(op, dict):
                continue
            name = op.get("op", "?")
            summary = f"op[{i}] {name}"
            if name in ("morph", "swap"):
                html = op.get("html") or ""
                summary += f" target={op.get('target')} html_bytes={len(str(html).encode())}"
            elif str(name).startswith("bridge."):
                summary += f" id={op.get('id')} pkg={op.get('package') or ''} method={op.get('method') or ''}"
                self.emit(
                    FrameKind.BRIDGE,
                    summary,
                    request_id=request_id,
                    trace_id=trace_id,
                    action=action,
                    detail={"op": op if self._config.capture_payloads else {"op": name}},
                )
                continue
            elif name == "toast":
                summary += f" {op.get('level', 'info')}: {op.get('message', '')[:80]}"
            elif name in ("navigate", "push_url"):
                summary += f" → {op.get('href')}"
            self.emit(
                FrameKind.OP,
                summary,
                request_id=request_id,
                trace_id=trace_id,
                action=action,
                detail={"index": i, "op": name, "target": op.get("target")},
            )


def _redact(obj: Any, keys: Sequence[str]) -> Any:
    keys_l = {k.lower() for k in keys}
    if isinstance(obj, dict):
        out = {}
        for k, v in obj.items():
            if str(k).lower() in keys_l or any(x in str(k).lower() for x in keys_l):
                out[k] = "***"
            else:
                out[k] = _redact(v, keys)
        return out
    if isinstance(obj, list):
        return [_redact(x, keys) for x in obj[:100]]
    return obj


def new_trace_id() -> str:
    return "tr_" + uuid.uuid4().hex[:16]


# Process singleton
_tracer: Optional[ChannelTracer] = None
_tracer_lock = threading.Lock()


def get_tracer() -> ChannelTracer:
    global _tracer
    with _tracer_lock:
        if _tracer is None:
            _tracer = ChannelTracer(TraceConfig(enabled=False))
        return _tracer


def set_tracer(tracer: ChannelTracer) -> None:
    global _tracer
    with _tracer_lock:
        _tracer = tracer


def enable_tracing(
    *,
    retain: int = 500,
    capture_payloads: bool = True,
) -> ChannelTracer:
    """Convenience for dev: turn on the global tracer."""
    t = get_tracer()
    t.configure(
        TraceConfig(enabled=True, retain=retain, capture_payloads=capture_payloads)
    )
    return t
