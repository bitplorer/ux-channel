"""
In-process WebRTC signaling metrics (P1).

Lightweight counters — no Prometheus required. Optional export via
``PrometheusMetrics`` if the host wires ``observe``.

Usage::

    from ux_channel.realtime.webrtc_metrics import rtc_metrics
    rtc_metrics.inc("signal_offer")
    rtc_metrics.snapshot()
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from typing import Any


@dataclass
class RtcMetrics:
    """Thread-safe counters for /rtc plane."""

    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)
    started_at: float = field(default_factory=time.time)
    counters: dict[str, int] = field(default_factory=dict)
    gauges: dict[str, float] = field(default_factory=dict)

    def inc(self, name: str, n: int = 1) -> None:
        with self._lock:
            self.counters[name] = int(self.counters.get(name, 0)) + int(n)

    def set_gauge(self, name: str, value: float) -> None:
        with self._lock:
            self.gauges[name] = float(value)

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return {
                "uptime_s": round(time.time() - self.started_at, 2),
                "counters": dict(self.counters),
                "gauges": dict(self.gauges),
            }

    def reset(self) -> None:
        with self._lock:
            self.counters.clear()
            self.gauges.clear()
            self.started_at = time.time()


rtc_metrics = RtcMetrics()


def note_signal(kind: str) -> None:
    rtc_metrics.inc("signals_total")
    rtc_metrics.inc(f"signal_{kind.replace('-', '_')}")


def note_ws(event: str) -> None:
    rtc_metrics.inc(f"ws_{event}")


def note_poll() -> None:
    rtc_metrics.inc("poll_total")


def note_auth_fail() -> None:
    rtc_metrics.inc("auth_fail")


def note_room_size(room: str, n: int) -> None:
    rtc_metrics.set_gauge(f"room_peers:{room[:32]}", n)
    # rolling max
    with rtc_metrics._lock:
        cur = rtc_metrics.gauges.get("room_peers_max", 0)
        if n > cur:
            rtc_metrics.gauges["room_peers_max"] = float(n)


__all__ = [
    "RtcMetrics",
    "rtc_metrics",
    "note_signal",
    "note_ws",
    "note_poll",
    "note_auth_fail",
    "note_room_size",
]
