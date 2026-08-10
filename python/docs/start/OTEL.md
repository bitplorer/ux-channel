# OpenTelemetry traces

### Brand lines

| Layer | Name |
|-------|------|
| **PyPI / pip** | `ux-channel` |
| **Import** | `ux_channel` |
| **CLI** | **`uxchannel`** |

## Boundary

| Layer | Owner |
|-------|--------|
| Protocol frames | `ux_channel.trace` (ChannelTracer) |
| OTel export | `ux_channel.otel` (optional) |
| TracerProvider / OTLP / Jaeger | **your app** |

```text
Intent → ChannelTracer frames → attach_otel() → OTel spans → your exporter
```

## Enable

```bash
pip install "ux-channel[otel]"
```

```python
from ux_channel import Channel, ChannelConfig

ch = Channel.boot(
    app,
    config=ChannelConfig.development(
        secret="…",
        observe="otel",   # auto setup_otel + attach_otel on boot
        allow_memory_stores=True,
    ),
)
```

Host-owned provider (recommended in production)::

```python
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry import trace

provider = TracerProvider()
provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter()))
trace.set_tracer_provider(provider)

# then boot Channel with observe="otel" — we will not replace your provider
```

## Span model

| Span | When |
|------|------|
| `ux.channel.request` | root per `request_id` on `intent.in` / `http` |
| `ux.channel.<kind>` | child frames (`handler.end`, `result.out`, …) |

Attributes (scalars only): `ux.action`, `ux.request_id`, `ux.duration_ms`, `ux.ok`, …

**No** intent args / result ops / secrets in attributes.

## DX dashboard

Use case **observability** shows:

* observe mode  
* OTel available / attached / provider class  
* open request roots  
* recent ChannelTracer frames (kind/action/ok/ms — no payloads)  
* guidance if something is missing  

```bash
uxchannel dashboard
```

## Manual API

```python
from ux_channel.otel import setup_otel, attach_otel, status, dashboard_snapshot

setup_otel(service_name="my-app")
attach_otel()
print(status())
print(dashboard_snapshot())
```
