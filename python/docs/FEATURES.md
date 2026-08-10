# ux-channel 0.1 — Feature encyclopedia

**Status:** complete product map for **0.1**  
**Brand:** PyPI `ux-channel` · import `ux_channel` · CLI `uxchannel`  
**Core loop:** **Intent → Action → Result(ops)**

This document catalogs **every major feature** of the library: what it is, when
to use it, public API, implementation modules, configuration, tests, and deep
docs. Deep format specs (e.g. CXB bytes) live in linked pages — this page is the
**feature index that leaves nothing to guess about what exists and where**.

If something is missing here, treat it as undocumented and fix this file in the
same change as the code.

---

## How to read this document

| Column / section | Meaning |
|------------------|---------|
| **Use when** | Product situations that justify the feature |
| **API** | Stable imports / entry points |
| **Implements** | Source modules (repo paths under `src/ux_channel/`) |
| **Config / env** | Knobs operators may set |
| **Tests** | Primary suites (under `tests/`) |
| **Docs** | Normative or how-to pages |

**Day-1 path only needs:** [GOLDEN_PATH](start/GOLDEN_PATH.md) + Channel + regions + ops.  
Everything else is **power / plane** import-by-home.

---

## 0. Product identity

| Item | Value |
|------|--------|
| Version | 0.1.0 (`ux_channel.__version__`) |
| License | MIT |
| Peer UI kit | optional **ux-dom** (not required) |
| Host model | Any ASGI/HTML host; FastAPI helpers first-class |
| Trust model | Capability tokens on Intent; fail closed on unsafe paths |

```python
from ux_channel import Channel, ChannelConfig, agents, state, attach_audit
```

---

## 1. Core control plane

### 1.1 Channel façade & boot

| | |
|--|--|
| **What** | Process façade: registry, config, ASGI mount, DX helpers |
| **Use when** | Every app — single entry to boot the control plane |
| **API** | `Channel`, `Channel.boot(app, config=...)`, `UiBuilder`, `sel` |
| **Implements** | `channel.py`, `factory.py`, `config.py`, `registry.py` |
| **Config** | `ChannelConfig.development` / production builders; secret, path, CSRF, wire |
| **Tests** | `tests/core/`, `tests/asgi/`, `tests/dx/` |
| **Docs** | [GOLDEN_PATH](start/GOLDEN_PATH.md) · [API_SURFACE](start/API_SURFACE.md) · [LAYERS](start/LAYERS.md) |

```python
ch = Channel.boot(app, config=ChannelConfig.development(secret="…32+ chars…"))
```

Default HTTP mount path is product-defined (override with config / env such as
`UX_CHANNEL_PATH` when documented in config). Do not hard-code private paths in
markup; use channel helpers that emit public attributes.

---

### 1.2 Intent, Result, ErrorObject

| | |
|--|--|
| **What** | Protocol documents: request (Intent), response (Result), structured errors |
| **Use when** | Always — the only control-plane exchange shape |
| **API** | `Intent`, `Result`, `ErrorObject`, `ActionError`, `ActionNotFound`, `ChannelError` |
| **Implements** | `types.py`, `errors.py`, `error_map.py`, `encode.py` |
| **Tests** | `tests/core/` |
| **Docs** | [RESULT](core/RESULT.md) · [ERRORS](core/ERRORS.md) · [CLIENT_ERRORS](core/CLIENT_ERRORS.md) |

**Result** carries `ok`, `ops[]`, optional `error`, `meta`.  
**Intent** carries `action`, `args`, `cap`, optional `target`, `request_id`, …

---

### 1.3 Ops (effect IR)

| | |
|--|--|
| **What** | Portable UI/control effects applied by the client (or other surfaces) |
| **Use when** | Any server decision that should change UI or client state |
| **API** | `ops.morph`, `toast`, `swap`, `navigate`, `push_url`, `reload`, `remove`, `focus`, `scroll`, `set_attr`, `set_text`, `signal_set`, `clear_errors`, `noop`, `bridge_*`, `dispatch`, … |
| **Implements** | `ops.py` |
| **Tests** | `tests/core/`, client/live suites |
| **Docs** | [RESULT](core/RESULT.md) · [JS_RUNTIME](client/JS_RUNTIME.md) |

Ops are **data**, not HTML templates. New op **types** are free strings; wire
dense keys for common fields are fixed in [CXB.md](core/CXB.md).

---

### 1.4 Actions & registry

| | |
|--|--|
| **What** | Named server handlers: `action` string → callable |
| **Use when** | Every interactive control that hits the server |
| **API** | `@ch.region` / `@on` patterns via Channel DX; `ActionRegistry`; `ActionContext`, `Principal` |
| **Implements** | `registry.py`, `context.py`, `channel.py`, `actions_file.py` |
| **Tests** | `tests/core/`, `tests/asgi/` |
| **Docs** | [HOW_TO](start/HOW_TO.md) · [COOKBOOK](start/COOKBOOK.md) |

Handlers receive context (principal, caps, state) and return `Result` or values
coerced to Result/ops.

---

### 1.5 Capability service (trust)

| | |
|--|--|
| **What** | Sign / verify capability tokens bound to actions and principals |
| **Use when** | Always in production; any Intent without a valid cap fails closed |
| **API** | `CapService`, `CapError`; attenuation helpers |
| **Implements** | `capability.py`, `attenuate.py`, `tree_cap.py`, `nonce.py` |
| **Config** | Channel secret; cap TTL / scope options on config |
| **Tests** | `tests/security/`, `tests/core/` |
| **Docs** | [SECURITY_AUDIT](security/SECURITY_AUDIT.md) · [PRINCIPLES](start/PRINCIPLES.md) |

**Law:** mesh membership ≠ trust. Caps authorize; transports only deliver.

---

### 1.6 Regions (paint surfaces)

| | |
|--|--|
| **What** | Named server-driven paint targets (`region` uid), not HTML tags |
| **Use when** | Partial page updates, multi-panel UIs, morph targets |
| **API** | `Region`, `RegionDef`, `RegionBook`, `RegionContext`, `RegionDirectory` |
| **Implements** | `region_component.py`, `regions.py`, region directory attach helpers |
| **Attrs** | Public `data-channel-*` / product attributes — never private filesystem paths |
| **Tests** | `tests/regions/` |
| **Docs** | [REGIONS](regions/REGIONS.md) · [COMPONENTS](regions/COMPONENTS.md) · [REGIONS_FS](regions/REGIONS_FS.md) |

---

### 1.7 Flow & navigation helpers

| | |
|--|--|
| **What** | Multi-step flows, fail paths, navigate/push helpers |
| **Use when** | Wizards, login/signup chains, post-action redirects |
| **API** | `Flow`, `FailFlow`, `attach_flow`, `Go`, `Navigate` |
| **Implements** | `flow.py`, `encode.py` |
| **Docs** | [HOW_TO](start/HOW_TO.md) · [PATTERNS](start/PATTERNS.md) |

---

## 2. Wire & serialization

### 2.1 Wire plane (all formats)

| | |
|--|--|
| **What** | Encode/decode Intent & Result for HTTP/WS; format + JSON engine policy |
| **Use when** | Every network boundary; default JSON for browsers |
| **API** | `ux_channel.wire`: `encode`, `decode`, `dumps`, `loads`, `configure_wire`, `available_formats`, `negotiate_*` |
| **Implements** | `wire/core.py`, `wire/negotiate.py`, `wire/__init__.py` |
| **Env** | `UX_CHANNEL_WIRE`, `UX_CHANNEL_WIRE_ENGINE`, `UX_CHANNEL_WIRE_WORKERS` |
| **Formats** | `json` (default) · `msgpack` · `cbor` · `cxb` |
| **JSON engines** | `auto` → orjson → ujson → stdlib |
| **Tests** | `tests/core/test_wire_*.py` |
| **Docs** | **[WIRE.md](core/WIRE.md)** |

Safety: soft configure falls back to JSON; `complete=True` recovery chain;
batch workers default sequential (opt-in parallelism).

**Internal only:** `ux_channel.wire.plugins` for custom format registration.

---

### 2.2 CXB (domain binary)

| | |
|--|--|
| **What** | Channel eXchange Binary — Intent/Result/ops native codec (CXB1 + CXBZ) |
| **Use when** | Server↔server, peers, bulk ops, density/latency paths (not required for browsers) |
| **API** | `format="cxb"`; `encode_cxb` / `decode_cxb`; oracle `*_python` |
| **Implements** | `wire/cxb.py` (Python oracle); `cxb_native/cxb_rs` (Rust default `.so`); pure Python oracle fallback |
| **Env** | `UX_CHANNEL_CXB_IMPL=auto\|native\|python` |
| **Build** | `./cxb_native/build.sh` |
| **Tests** | `tests/core/test_cxb_*.py`, `test_wire_cxb*.py` |
| **Docs** | **[CXB.md](core/CXB.md)** (complete) · [CXB_SPEED](core/CXB_SPEED.md) · [CXB_REALWORLD](core/CXB_REALWORLD.md) |

---

### 2.3 Serde / dumps convenience

| | |
|--|--|
| **What** | JSON dumps/loads always available for logging, dashboards, tooling |
| **API** | `dumps`, `loads`, `dumps_bytes`, `loads_bytes` (JSON-only) |
| **Docs** | [SERDE](start/SERDE.md) · [WIRE](core/WIRE.md) |

---

## 3. ASGI hosts & transports

### 3.1 FastAPI / Starlette integration

| | |
|--|--|
| **What** | Mount channel routes, middleware, dependency wiring |
| **Use when** | FastAPI/Starlette apps (primary host story) |
| **API** | `Channel.boot(app, …)`; `ux_channel.asgi` helpers |
| **Implements** | `asgi/fastapi.py`, `asgi/starlette.py`, `asgi/pipeline.py`, `asgi/core.py`, `middleware.py` |
| **Tests** | `tests/asgi/` |
| **Docs** | [FASTAPI](asgi/FASTAPI.md) |

---

### 3.2 WebSocket

| | |
|--|--|
| **What** | Bidirectional Intent/Result streaming |
| **Use when** | Live dashboards, progressive ops, low-latency control |
| **Implements** | ASGI websocket routes under channel |
| **Docs** | [WEBSOCKET](asgi/WEBSOCKET.md) |

---

### 3.3 SSE (Server-Sent Events)

| | |
|--|--|
| **What** | Server→client event stream of Results/ops |
| **Use when** | One-way live updates without full WS |
| **Docs** | [SSE](asgi/SSE.md) |

---

### 3.4 Live / push

| | |
|--|--|
| **What** | Push Results to connected clients; push security hooks |
| **Implements** | `live.py`, `push.py`, `push_security.py` |
| **Docs** | ASGI live docs · production push notes |

---

## 4. Client plane (browser)

### 4.1 JS runtime

| | |
|--|--|
| **What** | Browser runtime: submit Intent, apply ops, region morph, signals |
| **Use when** | Any browser UI driven by channel |
| **Implements** | static JS under package; client docs |
| **Tests** | `tests/client/`, live browser suites |
| **Docs** | **[JS_RUNTIME](client/JS_RUNTIME.md)** · [INTEROP](client/INTEROP.md) |

---

### 4.2 CSRF / host headers

| | |
|--|--|
| **What** | Channel-scoped CSRF / intent headers without fighting host frameworks |
| **Use when** | Cookie-session browser apps |
| **API** | `host_csrf.intent_headers`, related helpers |
| **Implements** | `host_csrf.py`, client header policy |
| **Docs** | **[CSRF_CHANNEL_HEADER](client/CSRF_CHANNEL_HEADER.md)** |

Design: do not hard-depend on a single framework header name; channel has its
own forward-looking header policy.

---

### 4.3 HTML safety & documents

| | |
|--|--|
| **What** | Safe HTML helpers, document assembly, attr escape |
| **API** | `SafeHtml`, `attr_escape`, `html`, `html_document`, `html_safe` |
| **Implements** | `html.py`, `html_document.py`, `html_safe.py` |

---

## 5. Bridges (JS / WASM islands)

### 5.1 Bridge ops & plane

| | |
|--|--|
| **What** | Mount/update/call/destroy third-party or custom client islands |
| **Use when** | Charts, editors, maps, vision widgets — not pure morph HTML |
| **API** | `ops.bridge_mount`, `bridge_update`, `bridge_call`, `bridge_destroy` |
| **Implements** | `bridge_*.py`, `bridges/`, `bridge_plane.py`, `bridge_api.py` |
| **Tests** | `tests/bridges/` |
| **Docs** | [BRIDGE_STRATEGY](bridges/BRIDGE_STRATEGY.md) · [BRIDGE_CONTRACT](bridges/BRIDGE_CONTRACT.md) · [PLUGINS](bridges/PLUGINS.md) · [NPM](bridges/NPM.md) · [MEDIA](bridges/MEDIA.md) |

---

### 5.2 Sealed protocol & guest runtime

| | |
|--|--|
| **What** | Allowlisted methods/events, payload ceilings, call budgets |
| **Use when** | Any untrusted or third-party bridge package |
| **API** | `SealedBridgeProtocol`, `GuestRuntime`, `BridgeManifest` via plugins hub |
| **Implements** | `bridge_protocol.py`, `guest_runtime.py`, `plugins.py` |
| **Docs** | [PLUGINS](bridges/PLUGINS.md) · foundations guest notes |

**Law:** same firewall mindset for future WASM islands (`runtime: wasm`).

---

## 6. State

| | |
|--|--|
| **What** | Server session / memory stores; SSR state; conflict detection |
| **Use when** | Multi-request user state, SSR hydration, optimistic guards |
| **API** | `state`, `attach_state`, `MemoryStateStore`, `NullStateStore`, `StateConflict`, `ssr_state`, `SessionVar`, `Namespace` |
| **Implements** | `state.py`, `ssr_state.py` |
| **Tests** | `tests/state/` |
| **Docs** | [STATE](state/STATE.md) · [SSR_STATE](state/SSR_STATE.md) |

**Law:** durable **Quantity** measures are not session chrome — use Quantity + store provenance.

---

## 7. Idempotency, limits, resilience

| Feature | Use when | API / modules | Docs |
|---------|----------|---------------|------|
| **Idempotency keys** | Safe retries of mutating actions | `MemoryIdempotencyStore`, intent fields | production / core |
| **Nonce store** | Replay resistance | `MemoryNonceStore`, `nonce.py` | security |
| **Limits** | Request size, rate-ish guards | `limits.py` | production |
| **Backoff** | Retry scheduling helpers | `backoff.py` | — |
| **Bulkhead** | Isolate overload | `bulkhead.py` | [CONCURRENCY](start/CONCURRENCY.md) |
| **Batch** | Batch encode/dispatch | `batch.py`, wire `encode_many` | WIRE |
| **Concurrency** | Parallel-safe defaults | `concurrency.py` | [CONCURRENCY](start/CONCURRENCY.md) |

---

## 8. Observability & DX

### 8.1 OpenTelemetry

| | |
|--|--|
| **What** | Traces/spans around Intent handling |
| **API / modules** | `otel.py`, attach helpers |
| **Docs** | [OTEL](start/OTEL.md) |

---

### 8.2 Metrics / Prometheus

| | |
|--|--|
| **What** | Prometheus-style metrics export hooks |
| **Implements** | `metrics_prom.py` |
| **Docs** | production observability |

---

### 8.3 Profiling (first-class DX)

| | |
|--|--|
| **What** | Latency measure helpers, suite runner, reports |
| **API** | `ux_channel.profiling` |
| **Implements** | `profiling.py` |
| **Tests** | `tests/core/test_p95_profiling.py` |
| **Docs** | DX / CONCURRENCY notes |

---

### 8.4 DX dashboard (pluggable)

| | |
|--|--|
| **What** | Operator dashboard for channel health / graphs; pluggable sections |
| **Use when** | Local DX, staging ops visibility — not a lock-in admin framework |
| **Implements** | `dx_dashboard.py`, `channel.py`, `dx_log.py`, `dx_errors.py` |
| **Docs** | [DASHBOARD](start/DASHBOARD.md) · [DX](dx/DX.md) · [INSPECTOR](dx/INSPECTOR.md) |

---

### 8.5 CLI

| | |
|--|--|
| **What** | `uxchannel` supercommand: info, doctor, scaffold, … |
| **API** | console script `uxchannel` · `python -m ux_channel` |
| **Implements** | `cli.py`, `__main__.py` |
| **Docs** | [SCAFFOLD](dx/SCAFFOLD.md) · README |

---

### 8.6 Explain / inspect / catalog

| Feature | Modules | Use |
|---------|---------|-----|
| Explain | `explain.py` | Human-readable action/result dumps |
| Inspect API | `inspect_api.py` | Dev inspection endpoints |
| Catalog | `catalog.py` | Action/region catalogs |
| Info | `info.py` | Runtime info for doctor |

---

## 9. Audit, forensics, intent log

| | |
|--|--|
| **What** | Append-only style intent logging, audit bundles, forensics queries |
| **Use when** | Compliance, debugging production incidents, agent oversight |
| **API** | `attach_audit`, `AuditBundle`, intent log helpers |
| **Implements** | `audit.py`, `intent_log.py`, `forensics.py`, `intent_sync.py` |
| **Docs** | foundations · production |

---

## 10. Agents (AX) & MCP

### 10.1 Agents façade

| | |
|--|--|
| **What** | Agent Experience API on top of the same Intent/Result bus |
| **Use when** | Tool-using agents, automated operators, multi-agent dispatch |
| **API** | `agents(ch)`, `Agents`, `attach_agents`, `agents_api` |
| **Implements** | `agents/`, `agents_api.py`, `agent_peer.py` |
| **Tests** | `tests/agents/` |
| **Docs** | **[AGENTS](agents/AGENTS.md)** · [AGENTS_MCP](agents/AGENTS_MCP.md) |

**Law:** AX is only `agents(ch)` — not a second framework.

---

### 10.2 MCP verticals

| | |
|--|--|
| **What** | Model Context Protocol oriented verticals (resources, sessions, effects, …) |
| **Implements** | `mcp/` (`resources`, `sessions`, `effects`, `subscribe`, `confirm`, …) |
| **Docs** | **[MCP_VERTICALS](agents/MCP_VERTICALS.md)** |

Shares Quantity/resource vocabulary with foundations where applicable.

---

## 11. Workplace, I/O channel, outbox

### 11.1 Workplace (rooms / mesh membership)

| | |
|--|--|
| **What** | Logical rooms and membership tickets for multi-surface work |
| **Use when** | Shop floor, multi-user ops rooms, scoped collaboration |
| **API** | `workplace`, `issue_mesh_membership`, room helpers |
| **Implements** | `workplace/` (`room.py`, `mesh.py`, `ticket.py`, …) |
| **Tests** | `tests/workplace/` |
| **Docs** | **[WORKPLACE](workplace/WORKPLACE.md)** · [WORKPLACE_OPS](workplace/WORKPLACE_OPS.md) · [THREE_SURFACES](workplace/THREE_SURFACES.md) |

---

### 11.2 I/O channel (not a device driver)

| | |
|--|--|
| **What** | Capability-shaped I/O gate: authorize methods; adapters perform |
| **Use when** | Scanners, lights, lab DUT, hardware-adjacent ops over **authorized channels** |
| **API** | `IoGate`, `IoProtocol`, `IoMethodSpec`, `IoKind`, `IoRoomClaim` |
| **Implements** | `io_channel.py`, `io_adapters/` |
| **Docs** | **[IO_CHANNEL](workplace/IO_CHANNEL.md)** · [FOUNDATIONS](foundations/FOUNDATIONS.md) |

**Law:** channel authorizes; adapters perform; mesh ≠ trust.

---

### 11.3 Outbox

| | |
|--|--|
| **What** | Reliable outbound effect queue / drain |
| **Use when** | At-least-once side effects after actions |
| **API** | `attach_outbox`, `drain_outbox` |
| **Implements** | `outbox.py` |
| **Docs** | [OUTBOX](workplace/OUTBOX.md) |

---

## 12. Foundations: Quantity, Morph IR, projections

### 12.1 Quantity

| | |
|--|--|
| **What** | Store-grounded measure: magnitude + unit + provenance (not “Money”) |
| **Use when** | Seats, stock, doses, currency amounts, any durable scalar with audit lineage |
| **API** | `Quantity.from_store(...)`, `QuantityBudget`, errors |
| **Implements** | `quantity.py` |
| **Docs** | [FOUNDATIONS](foundations/FOUNDATIONS.md) |

```python
from ux_channel.foundations.quantity import Quantity
q = Quantity.from_store(3, "seats", source="db.booking.1.seats", revision=1)
```

---

### 12.2 Morph IR

| | |
|--|--|
| **What** | Structural IR for building morph trees (`elem`, `region`, …) |
| **Use when** | Server-side composition of morph payloads beyond string HTML |
| **API** | `ux_channel.morph_ir` (`elem`, `region`, …) |
| **Implements** | `morph_ir.py` |
| **Docs** | foundations · regions |

---

### 12.3 Projections & placement

| | |
|--|--|
| **What** | Project domain objects into channel views; placement helpers |
| **Implements** | `projections.py`, `placement.py` |
| **Docs** | [PLACEMENT](start/PLACEMENT.md) |

---

### 12.4 Provenance

| | |
|--|--|
| **What** | Source/revision/principal lineage for store-grounded values |
| **Implements** | `provenance.py` (used by Quantity) |
| **Docs** | FOUNDATIONS |

---

## 13. WebRTC mesh

| | |
|--|--|
| **What** | Signaling, ICE, security for real-time mesh membership patterns |
| **Use when** | Browser/device mesh, not as a general game netcode stack |
| **Implements** | `webrtc/` (and docs) |
| **Tests** | `tests/webrtc/` |
| **Docs** | [WEBRTC](webrtc/WEBRTC.md) · [SIGNALING](webrtc/WEBRTC_SIGNALING.md) · [SECURITY](webrtc/WEBRTC_SECURITY.md) |

---

## 14. Planes, plugins hub, enterprise

| Feature | Role | Modules | Docs |
|---------|------|---------|------|
| **Planes** | Attach client/server plane helpers | `planes.py` | LAYERS |
| **Plugins hub** | Bridge manifests, validation | `plugins.py` | PLUGINS |
| **Enterprise** | Bundled enterprise knobs | `enterprise.py` | production |
| **Policy** | Policy hooks | `policy.py` | security |
| **CORS** | CORS helpers | `cors.py` | asgi |
| **Media** | Media helpers for bridges | `media.py` | [MEDIA](bridges/MEDIA.md) |
| **Codegen / scaffold** | Project generation | `codegen.py`, `bridge_scaffold.py` | SCAFFOLD |
| **Demo** | Demo app helpers | `demo.py` | EXAMPLES |

---

## 15. Security features (cross-cutting)

| Feature | Behavior |
|---------|----------|
| Capabilities | Required on Intent; verify before action |
| CSRF channel headers | Browser POST protection without host lock-in |
| Nonce / idempotency | Replay and double-submit resistance |
| Safe navigation | Block dangerous `navigate`/`href` patterns (`RISKY_SEGMENTS`) |
| HTML safety | Escape helpers; SafeHtml |
| Bridge guest firewall | Method allowlists + size/call ceilings |
| Wire CRC / ceilings | CXB integrity and DoS bounds |
| Push security | Authenticated push paths |

**Docs:** [SECURITY_AUDIT](security/SECURITY_AUDIT.md) · [PRODUCTION_CHECKLIST](production/PRODUCTION_CHECKLIST.md)

---

## 16. Concurrency & performance (cross-cutting)

| Feature | Default | Opt-in |
|---------|---------|--------|
| Wire encode/decode | Thread-safe, sequential batch | `UX_CHANNEL_WIRE_WORKERS` |
| CXB | Rust `.so` when built | `UX_CHANNEL_CXB_IMPL` |
| Action dispatch | Safe under load tests | bulkhead / limits |
| Client multi-region | Designed not to clobber | live DOM tests |

**Docs:** [CONCURRENCY](start/CONCURRENCY.md) · [CXB_SPEED](core/CXB_SPEED.md) · [UX_DOM_PERF](dx/UX_DOM_PERF.md)

---

## 17. Peer stack: ux-dom

| | |
|--|--|
| **What** | Optional HTML/component peer package; not bundled as mandatory |
| **Use when** | Python HTML components + channel regions together |
| **Glue** | `ux_channel_ux_dom` (if installed) |
| **Docs** | [STACK](start/STACK.md) · [BRIDGES_VS_UX_DOM](bridges/BRIDGES_VS_UX_DOM.md) |

Channel owns **control/trust/ops**; ux-dom owns **markup components**.

---

## 18. CLI feature map

```bash
uxchannel info          # versions, paths, health hints
uxchannel doctor        # environment / config diagnostics
uxchannel create-app …  # scaffold (see SCAFFOLD.md)
# additional subcommands as registered in cli.py — run uxchannel --help
```

Implementation: `cli.py`, entry points in `pyproject.toml` (`uxchannel`).

---

## 19. Configuration & environment (summary)

| Variable | Area | Role |
|----------|------|------|
| Channel secret / config object | Trust | Cap signing |
| `UX_CHANNEL_PATH` (when used) | ASGI | Mount path override |
| `UX_CHANNEL_WIRE` | Wire | Default format |
| `UX_CHANNEL_WIRE_ENGINE` | Wire | JSON engine |
| `UX_CHANNEL_WIRE_WORKERS` | Wire | Batch parallelism |
| `UX_CHANNEL_CXB_IMPL` | CXB | `auto` / `native` / `python` |

Authoritative config builders: `ChannelConfig` in `config.py`. Prefer config
objects in code over scattering env reads in app logic.

---

## 20. Testing map (by ontology)

| Plane | Path |
|-------|------|
| Core / wire / CXB | `tests/core/` |
| Regions | `tests/regions/` |
| State | `tests/state/` |
| ASGI | `tests/asgi/` |
| Bridges | `tests/bridges/` |
| Client | `tests/client/` |
| WebRTC | `tests/webrtc/` |
| Workplace | `tests/workplace/` |
| Agents | `tests/agents/` |
| Security | `tests/security/` |
| Stress | `tests/stress/` |
| DX | `tests/dx/` |
| Foundations | `tests/foundations/` |

```bash
pytest tests/core tests/regions tests/asgi -q
./cxb_native/build.sh && pytest tests/core/test_cxb_*.py -q
```

---

## 21. Use-case recipes (feature → path)

| You want… | Use |
|-----------|-----|
| First app | Channel.boot + region + toast/morph · GOLDEN_PATH |
| Login / signup style forms | Regions + Flow + caps + CSRF |
| Dense multi-op updates | Result ops; CXB on server hops |
| Chart / editor island | bridge_mount + sealed protocol |
| Agent tools on same bus | `agents(ch)` |
| Hardware-ish I/O | IoGate + adapter + room claim |
| Multi-user room | workplace + mesh membership |
| Durable numeric measure | Quantity.from_store |
| SSR + hydrate | ssr_state / attach_ssr_state |
| Live progressive UI | WS or SSE + push |
| Operator visibility | DX dashboard + OTEL + profiling |
| Production harden | SECURITY_AUDIT + PRODUCTION_CHECKLIST |

---

## 22. What was deliberately removed / renamed (0.1 clarity)

| Old idea | Now |
|----------|-----|
| `moat` package | Folded into organic modules |
| `Money` | **Quantity** |
| Morph HTML `slot` as brand | Morph IR `elem` / `region` (HTML slot is not the IR concept) |
| `UID_*` env legacy | `UX_CHANNEL_*` |
| Public wire plugin registration for apps | Internal `wire.plugins` only |
| Forced CXB for browsers | JSON default; CXB opt-in |

---

## 23. Documentation tree (complete)

```text
docs/
  FEATURES.md          ← this encyclopedia
  index.md · README.md
  start/               golden path, API, layers, concurrency, OTEL, dashboard…
  core/                RESULT, ERRORS, WIRE, CXB*
  regions/             regions, components
  state/               state, SSR
  asgi/                FastAPI, WS, SSE
  bridges/             strategy, contract, plugins, media, NPM
  client/              JS runtime, CSRF, interop
  webrtc/              mesh RTC
  workplace/           rooms, I/O channel, outbox
  agents/              AX, MCP
  foundations/         Quantity, IR, laws
  security/            audit
  production/          deploy, checklist
  dx/                  scaffold, examples, inspector
  book/                long-form narrative
```

Site nav: `mkdocs.yml`.

---

## 24. Source-of-truth rules

| Concern | Truth |
|---------|--------|
| Public day-1 imports | `ux_channel/__init__.py` + API_SURFACE.md |
| Feature list | **This file** |
| CXB bytes | CXB.md + `wire/cxb.py` |
| Wire policy | WIRE.md + `wire/core.py` |
| Security posture | SECURITY_AUDIT.md + capability/CSRF modules |
| Version | `ux_channel/_version.py` / `VERSION` |

**When you add a feature:** update code, tests, **and this encyclopedia** (and a deep doc if the feature is large).

---

## 25. Quick “what do I import?” card

```python
# Day-1
from ux_channel import Channel, ChannelConfig, agents, state, attach_audit
from ux_channel import toast, morph  # via ops re-export patterns in docs

# Wire
from ux_channel.wire import encode, decode, configure_wire

# Power
from ux_channel.foundations.quantity import Quantity
from ux_channel.foundations.io_channel import IoGate, IoRoomClaim
from ux_channel.workplace import workplace
from ux_channel.transport.outbox import attach_outbox, drain_outbox
from ux_channel.paint.morph_ir import elem, region
from ux_channel.security.host_csrf import intent_headers
from ux_channel.bridge.bridge_protocol import SealedBridgeProtocol
from ux_channel.bridge.guest_runtime import GuestRuntime
```

CLI: **`uxchannel`**.
