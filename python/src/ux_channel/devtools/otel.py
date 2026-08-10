# mypy: disable-error-code=import-not-found
# Copyright (c) 2026 UX-CHANNEL
"""OpenTelemetry integration for **ux-channel** (optional soft dependency).

Boundary (integrity)
--------------------
* Channel forensics live in :mod:`ux_channel.trace` (``TraceFrame`` ring).
* This module **subscribes** those frames and emits OTel spans when
  ``opentelemetry-api`` is installed and ``ChannelConfig.observe="otel"``.
* Apps own TracerProvider / exporters (OTLP, Jaeger, cloud). We never force
  a vendor or ship secrets into attributes.

Install::

    pip install ux-channel[otel]

Enable::

    ChannelConfig.development(..., observe="otel")
    # boot auto: setup_otel() + attach_otel()

Spans
-----
* One **request root** span per ``request_id`` (``ux.channel.request``).
* Child spans per frame (``ux.channel.<kind>``) under that root when possible.
* Attributes are scrubbed scalars only (``ux.*``).

Dashboard
---------
:func:`dashboard_snapshot` feeds the DX dashboard **observability** section —
observe-only: attach state + recent frame digest, never payloads.
"""

from __future__ import annotations

import logging
import threading
import time
from typing import Any, Optional

from ux_channel.devtools.trace import ChannelTracer, TraceFrame, get_tracer

logger = logging.getLogger("ux_channel.devtools.otel")

__all__ = [
    "attach_otel",
    "setup_otel",
    "otel_available",
    "detach_otel",
    "status",
    "dashboard_snapshot",
]

# Process state -------------------------------------------------------------
_attached = False
_on_frame = None
_lock = threading.RLock()
# request_id → (otel span, token) still open
_roots: dict[str, Any] = {}
_ROOT_KINDS = frozenset(
    {
        "intent.in",
        "http",
    }
)
_END_KINDS = frozenset(
    {
        "result.out",
        "handler.error",
        "cap.fail",
        "limit",
        "rate_limit",
    }
)
_MAX_ROOTS = 256


def otel_available() -> bool:
    try:
        import opentelemetry.trace  # noqa: F401  # type: ignore[import-not-found]

        return True
    except ImportError:
        return False


def setup_otel(
    *,
    service_name: str = "ux_channel",
    use_console_exporter: bool = False,
) -> bool:
    """Install a TracerProvider only if the host has not set one."""
    try:
        from opentelemetry import trace as otel_trace  # type: ignore[import-not-found]
        from opentelemetry.sdk.resources import Resource  # type: ignore[import-not-found]
        from opentelemetry.sdk.trace import TracerProvider  # type: ignore[import-not-found]
    except ImportError:
        logger.info("opentelemetry not installed — pip install ux-channel[otel]")
        return False

    provider = otel_trace.get_tracer_provider()
    if type(provider).__name__ in ("ProxyTracerProvider", "NoOpTracerProvider"):
        resource = Resource.create(
            {
                "service.name": service_name,
                "service.namespace": "ux-channel",
            }
        )
        provider = TracerProvider(resource=resource)
        if use_console_exporter:
            try:
                from opentelemetry.sdk.trace.export import (  # type: ignore[import-not-found]
                    BatchSpanProcessor,
                    ConsoleSpanExporter,
                )

                provider.add_span_processor(BatchSpanProcessor(ConsoleSpanExporter()))
            except Exception as exc:  # pragma: no cover
                logger.debug("console exporter unavailable: %s", exc)
        otel_trace.set_tracer_provider(provider)
        logger.info("otel TracerProvider installed service=%s", service_name)
    return True


def _set_attrs(span: Any, frame: TraceFrame) -> None:
    """Scalar attributes only — integrity: no nested payloads / secrets."""
    pairs: dict[str, Any] = {
        "ux.kind": frame.kind,
        "ux.summary": (frame.summary or "")[:512],
    }
    if frame.action:
        pairs["ux.action"] = frame.action
    if frame.request_id:
        pairs["ux.request_id"] = frame.request_id
    if frame.trace_id:
        pairs["ux.trace_id"] = frame.trace_id
    if frame.ok is not None:
        pairs["ux.ok"] = bool(frame.ok)
    if frame.duration_ms is not None:
        pairs["ux.duration_ms"] = float(frame.duration_ms)
    if frame.seq:
        pairs["ux.seq"] = int(frame.seq)
    if frame.detail:
        for k, v in list(frame.detail.items())[:24]:
            lk = str(k).lower()
            if k.startswith("_") or any(
                s in lk for s in ("secret", "token", "password", "authorization", "cookie")
            ):
                continue
            if isinstance(v, (str, int, float, bool)):
                pairs[f"ux.detail.{k}"] = v if not isinstance(v, str) else v[:256]
    for key, val in pairs.items():
        try:
            span.set_attribute(key, val)
        except Exception:
            continue


def _end_root(request_id: str, *, ok: Optional[bool], summary: str) -> None:
    from opentelemetry.trace import Status, StatusCode  # type: ignore[import-not-found]

    with _lock:
        entry = _roots.pop(request_id, None)
    if not entry:
        return
    span, token = entry
    try:
        if ok is False:
            span.set_status(Status(StatusCode.ERROR, (summary or "error")[:256]))
        else:
            span.set_status(Status(StatusCode.OK))
        span.end()
    except Exception:
        pass
    try:
        from opentelemetry import context as otel_context  # type: ignore[import-not-found]

        if token is not None:
            otel_context.detach(token)
    except Exception:
        pass


def _prune_roots() -> None:
    with _lock:
        if len(_roots) <= _MAX_ROOTS:
            return
        # drop oldest arbitrary keys
        for key in list(_roots.keys())[: len(_roots) - _MAX_ROOTS]:
            entry = _roots.pop(key, None)
            if not entry:
                continue
            span, token = entry
            try:
                span.end()
            except Exception:
                pass


def attach_otel(tracer: Optional[ChannelTracer] = None) -> bool:
    """Subscribe ChannelTracer frames → OpenTelemetry spans (idempotent)."""
    global _attached, _on_frame
    if _attached:
        return True

    try:
        from opentelemetry import context as otel_context  # type: ignore[import-not-found]
        from opentelemetry import trace as otel_trace  # type: ignore[import-not-found]
        from opentelemetry.trace import Status, StatusCode  # type: ignore[import-not-found]
    except ImportError:
        logger.warning(
            "observe=otel but opentelemetry-api not installed "
            "(pip install ux-channel[otel])"
        )
        try:
            from ux_channel.devtools.log import get_log

            get_log().warn(
                "OpenTelemetry not installed",
                event="otel_missing",
                hint="pip install ux-channel[otel]",
            )
        except Exception:
            pass
        return False

    tr = tracer or get_tracer()
    otel = otel_trace.get_tracer("ux_channel", schema_url="")

    def on_frame(frame: TraceFrame) -> None:
        rid = frame.request_id or ""
        kind = frame.kind or "custom"

        # Start request root on first protocol ingress for this request_id
        if rid and kind in _ROOT_KINDS:
            with _lock:
                has_root = rid in _roots
            if not has_root:
                span = otel.start_span(
                    "ux.channel.request",
                    attributes={"ux.request_id": rid},
                )
                if frame.action:
                    span.set_attribute("ux.action", frame.action)
                token = otel_context.attach(otel_trace.set_span_in_context(span))
                with _lock:
                    _roots[rid] = (span, token)
                _prune_roots()

        # Resolve parent context
        parent_ctx = None
        if rid:
            with _lock:
                entry = _roots.get(rid)
            if entry:
                parent_span, _tok = entry
                parent_ctx = otel_trace.set_span_in_context(parent_span)

        name = f"ux.channel.{kind}"
        with otel.start_as_current_span(name, context=parent_ctx) as span:
            _set_attrs(span, frame)
            if frame.ok is False:
                span.set_status(Status(StatusCode.ERROR, (frame.summary or "error")[:256]))
            else:
                span.set_status(Status(StatusCode.OK))

        # Close root on terminal frames
        if rid and kind in _END_KINDS:
            _end_root(rid, ok=frame.ok, summary=frame.summary or kind)

    tr.subscribe(on_frame)
    _on_frame = on_frame
    _attached = True
    logger.info("otel attached to ChannelTracer (request-scoped spans)")
    try:
        from ux_channel.devtools.log import get_log

        get_log().ok("OpenTelemetry attached", event="otel_attached")
    except Exception:
        pass
    return True


def detach_otel(tracer: Optional[ChannelTracer] = None) -> None:
    """Unsubscribe OTel sink (tests)."""
    global _attached, _on_frame
    if _on_frame is not None:
        tr = tracer or get_tracer()
        try:
            tr.unsubscribe(_on_frame)
        except Exception:
            pass
    _on_frame = None
    _attached = False
    with _lock:
        for rid in list(_roots.keys()):
            _end_root(rid, ok=None, summary="detach")
        _roots.clear()


def status() -> dict[str, Any]:
    """Compact OTel process status (safe for diagnose / dashboard)."""
    provider_name = None
    if otel_available():
        try:
            from opentelemetry import trace as otel_trace  # type: ignore[import-not-found]

            provider_name = type(otel_trace.get_tracer_provider()).__name__
        except Exception:
            provider_name = "unknown"
    with _lock:
        open_roots = len(_roots)
    return {
        "available": otel_available(),
        "attached": _attached,
        "provider": provider_name,
        "open_request_spans": open_roots,
        "observe_hint": 'ChannelConfig(..., observe="otel")',
        "install": "pip install ux-channel[otel]",
    }


def dashboard_snapshot(*, frame_limit: int = 12) -> dict[str, Any]:
    """Observe-only observability digest for the DX dashboard.

    Combines OTel attach state with a **scrubbed** ChannelTracer tail.
    Never includes intent args / result ops.
    """
    st = status()
    tr = get_tracer()
    enabled = bool(getattr(tr, "enabled", False))
    recent: list[dict[str, Any]] = []
    kind_counts: dict[str, int] = {}
    errors = 0
    if enabled:
        try:
            frames = tr.frames(limit=frame_limit)
        except TypeError:
            frames = tr.frames()[-frame_limit:]
        for f in frames[-frame_limit:]:
            kind_counts[f.kind] = kind_counts.get(f.kind, 0) + 1
            if f.ok is False:
                errors += 1
            recent.append(
                {
                    "seq": f.seq,
                    "kind": f.kind,
                    "action": f.action,
                    "ok": f.ok,
                    "duration_ms": f.duration_ms,
                    "request_id": f.request_id,
                    # no detail / payloads
                }
            )
    return {
        "otel": st,
        "channel_tracer": {
            "enabled": enabled,
            "recent_count": len(recent),
            "error_frames": errors,
            "kind_counts": kind_counts,
            "recent": recent,
        },
        "guidance": _guidance(st, enabled),
        "ts": time.time(),
    }


def _guidance(st: dict[str, Any], enabled: bool) -> list[str]:
    tips: list[str] = []
    if not st.get("available"):
        tips.append('Install OTel: pip install "ux-channel[otel]"')
    if st.get("available") and not st.get("attached"):
        tips.append('Set observe="otel" (or call attach_otel()) to export spans')
    if st.get("attached") and not enabled:
        tips.append(
            "OTel is attached but ChannelTracer is disabled — "
            "enable trace in config (observe=dev|otel maps this on boot)"
        )
    if st.get("attached") and enabled:
        tips.append("Traces flow: Channel frames → OTel spans (exporter is app-owned)")
    return tips
