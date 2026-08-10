# Python package layout — zones (not a flat dump)
> **Feeling lost in 100 top-level files?** You are not wrong — the tree grew flat.
> **Use zones** for intent. **Use `day1`** for app code. **Do not browse alphabetically.**

**Not stale:** package version tracks 0.1.0; monorepo gate (`make verify`) proves interop with Rust + day-1 regions. Zero TODO/FIXME markers in the host tree at generation time.

## How to open the package

```python
from ux_channel.day1 import Channel, Region, state  # apps
from ux_channel.zones import host, protocol
print(host.help())
print(protocol.MEMBERS)
```

```text
python/src/ux_channel/
  day1.py              ← preferred app imports
  zones/               ← INTENT MAP (this structure)
    protocol/          ← IR + wire + caps  (law w/ Rust)
    host/              ← Channel + regions + state
    render/            ← morph / HTML / placement
    security/          ← auth doors + limits
    transport/         ← ASGI / push / ws
    bridges_ui/        ← npm islands (not regions)
    agents_ax/         ← agents + MCP
    foundations/       ← quantity / workplace / io
    realtime_media/    ← webrtc / sfu
    ops_dx/            ← audit / CLI / obs
  <modules>.py         ← stable implementation paths (unchanged imports)
  wire/ asgi/ bridges/ … existing subpackages
```

## Zones at a glance

| Zone | Intent | Day-1? |
|------|--------|--------|
| **protocol** | Intent/Result/ops/caps/CXB | law |
| **host** | Channel, regions, actions, state | **yes** |
| **render** | HTML safety, morph, placement | via host |
| **security** | CSRF, attenuate, rate limits | as needed |
| **transport** | ASGI, push, websocket | host adapter |
| **bridges_ui** | npm widgets | optional |
| **agents_ax** | agents(ch), MCP | optional |
| **foundations** | quantity, workplace | power |
| **realtime_media** | WebRTC/SFU | optional |
| **ops_dx** | audit, CLI, metrics | ops |

## Zone `protocol`

Wire IR + codecs + capabilities — **shared law with Rust**. Start here for interop.

| Module | Intent |
|--------|--------|
| `types` | Intent / Result protocol types |
| `ops` | Result op builders (morph, toast, …) |
| `errors` | Channel error types |
| `error_map` | Error code → HTTP / client kind |
| `capability` | Cap sign/verify (args_hash law) |
| `encode` | Lift Python returns into Result |
| `serde` | JSON dumps/loads helper (prefer wire) |
| `jsonutil` | JSON depth/breadth safety |
| `wire` | SUBPACKAGE: JSON/CXB codecs + negotiate |
| `py.typed` | PEP 561 marker |

## Zone `host`

Channel, regions, actions, state — **day-1 application surface**.

| Module | Intent |
|--------|--------|
| `day1` | Narrow day-1 import façade |
| `dx` | Channel façade (boot, control, done) |
| `config` | ChannelConfig |
| `registry` | Action dispatch kernel |
| `context` | ActionContext / Principal |
| `regions` | RegionBook + @region |
| `region_component` | Class-style Region |
| `region_directory` | Opt-in FS region discovery |
| `region_cli` | CLI scaffold for regions |
| `flow` | on / done / fail / refresh verbs |
| `factory` | Bootstrap helper |
| `hooks` | Action lifecycle hooks |
| `state` | Draft / state stores |
| `state_api` | state(ch) day-1 API |
| `ssr_state` | Session values for re-paint |
| `planes` | Client/db safety helpers for state |
| `live` | In-process topic → region bind |
| `nonce` | One-shot / nonce store |
| `idempotency` | Idempotency store |
| `actions_file` | File-based action discovery |
| `catalog` | Action catalog metadata |
| `testing` | ChannelTest helpers |
| `recipes` | Named day-1 patterns |

## Zone `render`

HTML safety, morph IR, placement — **how paint reaches the client**.

| Module | Intent |
|--------|--------|
| `html` | Control attrs / demo HTML helpers |
| `html_safe` | SafeHtml / esc |
| `html_document` | Document Placement (no HTML strings) |
| `morph_ir` | Multi-surface morph IR |
| `projections` | Project morph IR to surfaces |
| `placement` | Framework-agnostic attrs/scripts |
| `render` | HtmlRenderer protocol |
| `slot_compile` | Stable uid compile from trees |
| `response` | FastAPI/Starlette HTML responses |
| `demo` | Demo SSR markup only |
| `static` | SUBPACKAGE: client JS (ux-channel.js) |

## Zone `security`

CSRF, attenuate, limits, auth doors — **authority hardening**.

| Module | Intent |
|--------|--------|
| `host_csrf` | CSRF forwarding / channel CSRF |
| `security` | HTTP + apply-op security helpers |
| `security_events` | Structured security event stream |
| `attenuate` | Cap attenuation (narrow only) |
| `tree_cap` | Capability-shaped document trees |
| `policy` | Optional allow/deny hooks |
| `push_security` | SSE/push subscribe auth |
| `ws_security` | WebSocket auth doors |
| `ratelimit` | Action rate limits |
| `bulkhead` | Concurrency bulkhead |
| `limits` | Result size limits |

## Zone `agents_ax`

Agent Experience + MCP — **tools/situation, not core UI regions**.

| Module | Intent |
|--------|--------|
| `agents_api` | agents(ch) AX façade |
| `agent_peer` | Internal agent Intent path |
| `agents` | SUBPACKAGE: agent runners/tools |
| `mcp` | SUBPACKAGE: MCP tool plane |

## Zone `transport`

ASGI, push, WS, batch — **how Intents arrive**.

| Module | Intent |
|--------|--------|
| `asgi` | SUBPACKAGE: HTTP/ASGI adapters |
| `batch` | Batch Intent dispatch |
| `stream` | SSE progressive Results |
| `push` | Server push bus |
| `cors` | CORS helper |
| `middleware` | ASGI middleware helpers |
| `ws_protocol` | WebSocket message helpers |
| `ws_limits` | WebSocket rate limits |
| `backoff` | Retry backoff strategies |
| `concurrency` | Internal parallel dispatch |
| `outbox` | Intent outbox queue |
| `intent_sync` | Cross-worker intent sync |
| `redis_extra` | SUBPACKAGE: Redis stores (optional) |

## Zone `bridges_ui`

npm islands + optional components — **not regions**.

| Module | Intent |
|--------|--------|
| `bridge_api` | Bridge API entry |
| `bridge_plane` | Bridge plane data+ops |
| `bridge_contract` | Bridge contracts |
| `bridge_protocol` | Sealed bridge protocols |
| `bridge_scaffold` | Scaffold npm bridges |
| `bridge_preset_gen` | Generate bridge presets |
| `bridge_style` | Bridge host chrome CSS |
| `bridges` | SUBPACKAGE: Chart/Leaflet/… presets |
| `components` | SUBPACKAGE: optional ChannelComponent kit |
| `guest_runtime` | Sealed guest islands |
| `plugins` | Plugin hub |

## Zone `foundations`

Quantity, provenance, I/O, workplace — **domain integrity**.

| Module | Intent |
|--------|--------|
| `quantity` | Store-grounded measures |
| `provenance` | Source stamps for sensitive values |
| `io_channel` | I/O channel authorize/record |
| `io_adapters` | SUBPACKAGE: sample I/O adapters |
| `workplace` | SUBPACKAGE: rooms/mesh/tickets |

## Zone `realtime_media`

WebRTC / SFU / media — **optional realtime planes**.

| Module | Intent |
|--------|--------|
| `webrtc` | WebRTC signaling plane |
| `webrtc_http` | WebRTC HTTP helpers |
| `webrtc_metrics` | WebRTC metrics |
| `webrtc_turn` | TURN credentials |
| `webrtc_ui` | WebRTC plugin surface |
| `sfu` | SFU adapter surface |
| `whip` | WHIP/WHEP helpers |
| `media` | Media plane + LiveKit DX |

## Zone `ops_dx`

Audit, CLI, observability — **operate and diagnose**.

| Module | Intent |
|--------|--------|
| `audit` | attach_audit intent log+forensics |
| `intent_log` | Ordered Intent log |
| `forensics` | Reconstruct painted frames |
| `trace` | Action/bridge tracing |
| `explain` | Teachable error recipes |
| `inspect_api` | Live inspect (prod-closed) |
| `observability` | Logging/metrics hooks |
| `otel` | OpenTelemetry (optional) |
| `metrics_prom` | Prometheus sink (optional) |
| `profiling` | Maintainer profiling |
| `dx_errors` | CLI/DX exceptions |
| `dx_log` | DX console logging |
| `dx_dashboard` | Operator dashboard |
| `info` | Package/runtime info |
| `upgrade_check` | Scan projects for outdated patterns |
| `cli` | uxchannel CLI |
| `__main__` | python -m ux_channel |
| `_version` | Package version |
| `codegen` | TS client codegen (optional) |
| `enterprise` | Multi-tenant helpers |
| `pydantic_actions` | Pydantic-validated actions (opt) |
| `schema_models` | Optional Pydantic IR models |
| `ticket_revoke` | Revoke live push tickets |
| `scaffold` | SUBPACKAGE: project scaffold templates |

## Stability rules

1. **Import paths** `ux_channel.regions`, `ux_channel.capability`, … stay valid (no mass rename).
2. **Zones** are the map; they may grow without moving files until a major version.
3. **Day-1 apps** only need `ux_channel.day1` + ONTOLOGY.
4. **Rust interop** only requires zone `protocol` (types/ops/caps/wire).
5. **Regenerate** this catalog: `python3 scripts/gen_python_layout.py`.
