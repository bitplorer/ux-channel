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

**No top-level module aliases. No day1 / dx / ops_dx / paint / zones jargon packages.**

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
| `day1` | `api` |
| `host.dx` / `dx.py` | `host.channel` |
| `ops_dx` | `devtools` |
| `dx_dashboard` / `dx_log` | `dashboard` / `log` |
| `bridge_meta` | `bridge` |
| `paint` | `render` |
| `paint.render` | `render.renderers` |
| `paint.demo` | `render.kit` |
| `zones` | `catalog` |
| `recipes` | `patterns` |
| `jsonutil` | `json_codec` |
| `planes` | `state_planes` |
| `mental_model()` | `Channel.describe()` |
| `CapService.sign` | `CapService.mint` |

## Change process

1. Code goes in the correct package (`PACKAGE_MAP.json`).
2. `python3 scripts/sync_python_layout.py` then `--check`.
3. Export public symbols only via root / `api` / package `__init__` (`MANUAL_PUBLIC_API`).
4. `make verify` + `make test-python-host`.
