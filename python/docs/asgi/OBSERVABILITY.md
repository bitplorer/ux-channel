# Observability — JSON logs + OpenTelemetry

## Structured JSON logging (automation)

### CLI DX logs

```bash
ux_channel --json bridge new chartjs --out bridges
ux_channel --json -v bridge add-method chartjs resetZoom --out bridges

# or
export UX_CHANNEL_DX_JSON=1
uxchannel bridge methods chartjs --out bridges
```

One JSON object per line (stderr):

```json
{"ts":1710000000.12,"level":"ok","msg":"added method","event":"ok","method":"resetZoom","logger":"ux_channel.dx","service":"ux_channel"}
```

| Field | Meaning |
|-------|---------|
| `ts` | Unix time |
| `level` | debug \| info \| ok \| warn \| error |
| `msg` | Human message |
| `event` | Machine event id when set |
| `code` / `hint` | On DxError |
| `logger` | `ux_channel.dx` |

### Action hooks

```python
from ux_channel.devtools.observability import observability_after_hook
reg.after(observability_after_hook(json_logs=True, log_slow_ms=100))
```

## OpenTelemetry (distributed tracing)

**Optional.** Protocol forensics stay in `ChannelTracer`; OTel is a **subscriber**.

```bash
pip install ux-channel[otel]
```

```python
cfg = ChannelConfig.production(
    secret=...,
    observe="otel",   # off | dev | otel
    allow_memory_stores=True,  # or Redis
)
ch = Channel.boot(app, config=cfg)
```

Or manual:

```python
from ux_channel.devtools.otel import setup_otel, attach_otel, status
setup_otel(service_name="myapp")  # respects existing TracerProvider
attach_otel()
print(status())
```

### Span model

| Span name | Source |
|-----------|--------|
| `uid.intent_in` | Incoming Intent |
| `uid.handler_start` / `handler_end` | Action body |
| `uid.result_out` | Result |
| `uid.cap_fail` / `cap_ok` | Capability |
| `uid.bridge` / `uid.op` | Bridge ops |

Attributes: `uid.action`, `uid.request_id`, `uid.ok`, `uid.duration_ms`, …

**App owns exporters** (OTLP, Jaeger, cloud). Channel never pins a vendor.

### Config

| `observe` | Behavior |
|-----------|----------|
| `off` | No OTel attach |
| `dev` | Channel trace ring (DX) |
| `otel` | Trace + soft OTel attach |

## Separation of concerns

```text
DxLog (--json)     → CLI / scaffolding automation
observability hook → per-action metrics + logs
ChannelTracer      → protocol frame ring
otel.py            → optional bridge TraceFrame → OTel spans
```
