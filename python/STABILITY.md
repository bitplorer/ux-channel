# Python host — single truth

## Mental model (one line)

**Intent in → trusted action → Result ops out.**  
You own HTML; Channel owns control, trust, regions, and ops.

## Layout law

```text
ux_channel/
  __init__.py       frozen public re-exports
  api/              curated application surface (same objects as root)
  protocol/         Intent, Result, CapService, ops  (Rust-parity)
  host/             Channel, Region, RegionBook, state_api, stores
  render/           morph IR, HTML safety, placement, renderers, kit
  security/         CSRF, limits, attenuate
  transport/        batch, push, stream helpers
  foundations/      quantity, provenance, io
  realtime/         WebRTC / media
  bridge/           contracts + scaffold
  bridges/          npm island presets
  wire/             JSON / CXB codecs
  asgi/             FastAPI / Starlette mount
  devtools/         audit, CLI, observability
  catalog/          package navigator
  PACKAGE_MAP.json  module → package map (no shims)
```

**Forbidden package names (must not reappear):**  
`day1`, `ops_dx`, `bridge_meta`, `paint`, `zones`, `security_plane`, `host/dx.py`, `host/state.py` (use `host/stores.py`).

## Identity law

```text
ux_channel.Channel     ≡  api.Channel     ≡  host.Channel
ux_channel.CapService  ≡  protocol.CapService
ux_channel.state        ≡  host.state_api.state
ux_channel.morph       ≡  protocol morph builder
```

Gate tests freeze these. Never invent a second CapService or Channel.

## Stores vs state API

| Import | What |
|--------|------|
| `from ux_channel import state` | Application `state(channel)` API |
| `from ux_channel.host.state_api import state` | Same function |
| `from ux_channel.host.stores import MemoryStateStore` | Persistence backends |

## Import flow

```python
# Application
from ux_channel import Channel, Region, CapService, state, morph
from ux_channel.api import Channel, Region, CapService, state

# By package intent
from ux_channel.protocol import CapService, Intent, Result, morph, toast
from ux_channel.host import Channel, Region, RegionBook
from ux_channel.host.stores import MemoryStateStore
from ux_channel.render import esc, morph_ir, renderers
from ux_channel.security import intent_headers, safe_href
from ux_channel.wire import encode, decode, encode_cxb
from ux_channel.asgi import mount_channel
from ux_channel.devtools import attach_audit
```

## Package public APIs

Every package ``__init__.py`` is **hand-maintained** (human-owned exports).
Layout sync only regenerates ``catalog/catalog.json`` — it never overwrites
package inits. There is **no** env var or Python symbol named
``hand-maintained package init`` (that was a temporary magic comment; removed).

| Package | Primary exports |
|---------|-----------------|
| `protocol` | `CapService`, `Intent`, `Result`, `morph`, `toast`, … |
| `host` | `Channel`, `Region`, `RegionBook`, `create_channel` |
| `render` | `morph_ir`, `esc`, `renderers`, … |
| `security` | `intent_headers`, `attenuate`, `safe_href` |
| `wire` | `encode`, `decode`, `encode_cxb`, `MEDIA_TYPES` |
| `asgi` | `mount_channel` |
| `devtools` | `attach_audit`, `inspect_channel` |
| `foundations` | `Quantity` |
| `agent_runtime` | `AgentRunner`, `AgentPolicy`, `AgentPeer`, … |

Deep modules: `ux_channel.<package>.<module>`.

## Rename history (do not reintroduce)

| Forbidden (old) | Use instead |
|-----------------|-------------|
| `day1` | `api` |
| `host/dx.py` | `host/channel.py` |
| `ops_dx` | `devtools` |
| `dx_dashboard` / `dx_log` / `dx_errors` | `dashboard` / `log` / `errors` |
| `bridge_meta` | `bridge` |
| `paint` | `render` |
| `paint.render` | `render.renderers` |
| `paint.demo` | `render.kit` |
| `zones` | `catalog` |
| `recipes` | `patterns` |
| `jsonutil` | `json_codec` |
| `planes` | `state_planes` |
| `host/state.py` (stores) | `host/stores.py` |
| `mental_model()` | `Channel.describe()` |
| `CapService.sign` | `CapService.mint` |
| `DAY1_*_API` | `CHANNEL_PUBLIC_API` / `WEBRTC_PUBLIC_API` / `MEDIA_PUBLIC_API` |

## Change process

1. Put code in the correct package (`PACKAGE_MAP.json`).
2. `python3 scripts/sync_python_layout.py` then `--check`.
3. Public symbols only via root / `api` / package `__init__`.
4. `make verify` (health + layout + gate + rust + uxc_check).


## agents() vs agent_runtime

| Name | Kind |
|------|------|
| `agents(ch)` | Function façade (root / api) |
| `ux_channel.agent_runtime` | Implementation package |

Never name a package `agents` — it shadows the function on `ux_channel`.


## Caller planes (runtimes)

| Name | Role |
|------|------|
| (default) Channel | Human Intent path |
| `agent_runtime` | Non-human tool kernel (`AgentRunner`, `peer`, policy, session) |
| `bridge.guest_runtime` | Sealed island guest |
| `mcp` | MCP adapter **on top of** agent_runtime |
| `workplace` | Room policy / tickets (not a tool runner) |

`agents()` is a **function** façade. Implementation package is `agent_runtime` (never `agents/`).


## Catalog disambiguation

| Path | Role |
|------|------|
| `ux_channel.catalog` | Package navigator (layout map) |
| `ux_channel.host.action_catalog` | Action registry metadata for docs/codegen |
| `agent_runtime.tool_audit` | Agent tool-call audit sinks |
| `devtools.audit` | Channel Intent audit / forensics façade |


## PACKAGE_MAP v3

Module keys are ``package.stem`` (unique), so short names may repeat:

| Key | Module |
|-----|--------|
| `security.policy` | CSRF/security policy |
| `agent_runtime.policy` | Agent allow/deny policy |
| `protocol.errors` | Channel/action errors |
| `devtools.errors` | Teachable DX errors |

Catalog lists full import paths. Layout check fails if any on-disk module is unmapped.
