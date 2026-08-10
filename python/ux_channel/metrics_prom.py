"""Prometheus metrics sink (optional)."""

from __future__ import annotations

from typing import Dict


class PrometheusMetrics:
    """Minimal counters/histograms without requiring prometheus_client at import."""

    def __init__(self) -> None:
        self.counters: Dict[str, float] = {}
        self.timings: Dict[str, list] = {}

    def incr(self, name: str, value: float = 1.0, **tags: str) -> None:
        key = _key(name, tags)
        self.counters[key] = self.counters.get(key, 0.0) + value

    def timing(self, name: str, ms: float, **tags: str) -> None:
        key = _key(name, tags)
        self.timings.setdefault(key, []).append(ms)

    def render_prometheus(self) -> str:
        lines = []
        for k, v in sorted(self.counters.items()):
            lines.append(f"# TYPE {k.split('{')[0]} counter")
            lines.append(f"{k} {v}")
        for k, vals in sorted(self.timings.items()):
            if not vals:
                continue
            avg = sum(vals) / len(vals)
            lines.append(f"# TYPE {k.split('{')[0]} gauge")
            lines.append(f"{k}_avg {avg}")
            lines.append(f"{k}_count {len(vals)}")
        return "\n".join(lines) + "\n"


def _key(name: str, tags: dict) -> str:
    if not tags:
        return name.replace(".", "_")
    inner = ",".join(f'{k}="{v}"' for k, v in sorted(tags.items()))
    return f"{name.replace('.', '_')}{{{inner}}}"


def metrics_asgi_app(metrics: "PrometheusMetrics | None" = None):
    """
    Return a minimal ASGI app that serves Prometheus text if metrics provided.

    Mount via Starlette/FastAPI as needed, or use host GET /ux-channel/metrics.
    """
    async def app(scope, receive, send):
        if scope["type"] != "http":
            return
        body = b""
        if metrics is not None and hasattr(metrics, "render"):
            try:
                body = metrics.render().encode("utf-8")
            except Exception:
                body = b"# metrics unavailable\n"
        elif metrics is not None and hasattr(metrics, "to_prometheus"):
            body = str(metrics.to_prometheus()).encode("utf-8")
        else:
            body = b"# uxchannel metrics not configured\n"
        await send({"type": "http.response.start", "status": 200,
                    "headers": [[b"content-type", b"text/plain; version=0.0.4"]]})
        await send({"type": "http.response.body", "body": body})
    return app
