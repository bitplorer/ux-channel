# Python host — single truth

## Mental model (one line)

**Intent in → trusted action → Result ops out.**  
You own HTML; Channel owns control, trust, regions, and ops.

## Layout law

Long-term strata + extension doors: [../LONGEVITY.md](../LONGEVITY.md).  
Ceremonial vs hand-coded: [../AUTOMATION.md](../AUTOMATION.md).

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
  LAYERS.md         one-page map — read this before sibling folders
  realtime/         WebRTC / media (L4; lazy on Channel)
  bridge/           contracts + scaffold (L4; lazy on Channel)
  bridges/          npm island presets (L4)
  wire/             JSON / CXB codecs
  asgi/             FastAPI / Starlette mount
  devtools/         audit, CLI, observability
  catalog/          package navigator (GENERATED catalog.json)
  PACKAGE_MAP.json  packages inventory; modules/count are derived
  cek/              wrap of cek-runtime Host (L3; default cek=require; Cap machine only; cek=off imports nothing)
```

**Forbidden package names (must not reappear):**  
`day1`, `ops_dx`, `bridge_meta`, `paint`, `zones`, `security_plane`, `host/dx.py`, `host/state.py` (use `host/stores.py`).

## Root surface

* Root binds **only** the application / stable core (see ``__all__``).
* Power modules are **not** re-exported on root — import packages::

      from ux_channel.host.stores import MemoryStateStore
      from ux_channel.host.testing import ChannelTest

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

Every package ``__init__.py`` export list is **hand-maintained** (public API is design).  
Layout sync **always regenerates** ``catalog/catalog.json`` and the derived ``modules`` /
``module_count`` fields in ``PACKAGE_MAP.json``. It never overwrites package inits.

```bash
make regen       # write derived artifacts
make layout      # CI: fail if stale
make sync-map    # opt-in: packages ← disk inventory
```

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
One-line package intent also lives in `PACKAGE_MAP.json` → `package_docs`.

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
