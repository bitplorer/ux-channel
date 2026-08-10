# Python host — single truth (professional packages)

## Layout law

```text
ux_channel/
  __init__.py          # frozen public re-exports
  api/                 # curated application surface
  protocol/            # Intent, Result, CapService, ops (Rust-parity)
  host/                # Channel, Region, RegionBook, state, registry
  render/              # morph IR, HTML safety, placement, renderers
  security/            # CSRF, limits, attenuate
  transport/           # batch, push, ws helpers
  foundations/         # quantity, provenance, io
  realtime/            # WebRTC / media
  bridge/              # bridge contracts / scaffold
  bridges/             # npm island presets
  devtools/            # audit, CLI, observability, dashboards
  asgi/ wire/ agents/ mcp/ workplace/ …
  catalog/             # package navigator (not an implementation plane)
  PACKAGE_MAP.json
```

**No top-level module aliases. No api / dx / devtools / paint / zones jargon packages.**

## Import flow

```python
from ux_channel import Channel, Region, CapService, state
from ux_channel.api import Channel, Region, CapService   # same objects, narrow

from ux_channel.protocol import CapService, Intent, Result, morph, toast
from ux_channel.host import Channel, Region, RegionBook
from ux_channel.host.channel import Channel             # implementation module
from ux_channel.render import morph_ir, renderers
from ux_channel.devtools import audit
from ux_channel.bridge import bridge_plane
```

## Rename history (do not reintroduce)

| Forbidden | Use instead |
|-----------|-------------|
| `api` | `api` |
| `host.channel` / `dx.py` | `host.channel` |
| `devtools` | `devtools` |
| `dx_dashboard` / `dx_log` | `dashboard` / `log` |
| `bridge` | `bridge` |
| `paint` | `render` |
| `paint.render` | `render.renderers` |
| `paint.demo` | `render.kit` |
| `zones` | `catalog` |
| `recipes` | `patterns` |
| `json_codec` | `json_codec` |
| `planes` | `state_planes` |
| `describe()` | `Channel.describe()` |
| `CapService.mint` | `CapService.mint` |

## Change process

1. Code goes in the correct package (`PACKAGE_MAP.json`).
2. `python3 scripts/sync_python_layout.py` then `--check`.
3. Export public symbols only via root / `api` / package `__init__` (`MANUAL_PUBLIC_API`).
4. `make verify` + `make test-python-host`.


## Package public APIs

Cohesive packages may expose a small set on the package root
(`MANUAL_PUBLIC_API` marker — `sync_python_layout` will not overwrite):

| Package | Example |
|---------|---------|
| `protocol` | `CapService`, `Intent`, `morph` |
| `host` | `Channel`, `Region`, `RegionBook` |
| `render` | `morph_ir`, `renderers` |
| `security` | `intent_headers`, `attenuate` |
| `foundations` | `Quantity` |

Deep modules remain available as `ux_channel.<package>.<module>`.


## Name collisions to respect

| Path | Meaning |
|------|---------|
| `ux_channel.host.stores` | **Module** — memory/null stores (`MemoryStateStore`) |
| `ux_channel.host.state_api.state` | **Function** — application `state(ch)` API |
| `from ux_channel import state` | The function (root re-export) |

The store module is `host.stores` (not `host.state`) so `state()` never collides.


## Identity law

```text
ux_channel.Channel  is  ux_channel.api.Channel  is  ux_channel.host.Channel
ux_channel.CapService is ux_channel.protocol.CapService
ux_channel.state     is  ux_channel.host.state_api.state
ux_channel.morph    is  ux_channel.protocol.ops.morph  (via protocol package)
```

Gate tests freeze these identities. Never create a second CapService/Channel.

## Stores vs state API

| Import | What |
|--------|------|
| `from ux_channel import state` | Application `state(channel)` API |
| `from ux_channel.host.stores import MemoryStateStore` | Persistence backends |
| `from ux_channel.host.state_api import state` | Same as root `state` |
