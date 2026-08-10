# Python host — single truth (no shims)

## Layout law

```text
ux_channel/
  __init__.py          # frozen public re-exports
  api/                # app-facing surface (same symbols, intentional package)
  protocol/            # Intent, Result, CapService, ops  (Rust-parity)
  host/                # Channel, Region, RegionBook, state, registry
  paint/               # morph, HTML, placement
  security/            # CSRF, limits, attenuate
  transport/           # batch, push, ws helpers
  foundations/         # quantity, provenance, io
  realtime/            # webrtc / media
  bridge/         # bridge contracts
  devtools/              # audit, CLI, observability
  wire/ asgi/ bridges/ components/ agents/ mcp/ workplace/ …
  PACKAGE_MAP.json     # module → package inventory
```

**There are no top-level `ux_channel/foo.py` aliases.**  
If a module moved, you import the package path.

## Import flow (cognitive)

```text
App code     →  ux_channel.api  or  ux_channel (public symbols)
Extensions   →  ux_channel.host.* / protocol.* / paint.* / …
Shared law   →  CapService.mint/verify  (same as Rust)
```

```python
# Apps
from ux_channel.api import Channel, Region, CapService, state

# By package (preferred power imports)
from ux_channel.protocol import CapService, Intent, Result, morph
from ux_channel.host import Channel, Region, RegionBook
from ux_channel.paint import morph_ir
```

## Change process

1. Put code in the correct package (see PACKAGE_MAP / package_docs).  
2. `python3 scripts/sync_python_layout.py` (refreshes package `__init__` + catalog).  
3. `python3 scripts/sync_python_layout.py --check` must pass (CI).  
4. Export new public symbols only via root `__init__` + `api` if they are application API.  
5. `make verify` and `make test-python-host`.

## Tests

| Tier | Command |
|------|---------|
| Gate | `make verify` |
| Host | `make test-python-host` |

## Forbidden

- Top-level shim/alias modules  
- Dual names for Rust surface (`sign` vs `mint`, etc.)  
- Re-introducing flat `ux_channel/<100 modules>.py`
