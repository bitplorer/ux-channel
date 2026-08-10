# Python host — single truth (no shims)

## Layout law

```text
ux_channel/
  __init__.py          # frozen public re-exports
  day1/                # app-facing surface (same symbols, intentional package)
  protocol/            # Intent, Result, CapService, ops  (Rust-parity)
  host/                # Channel, Region, RegionBook, state, registry
  paint/               # morph, HTML, placement
  security/            # CSRF, limits, attenuate
  transport/           # batch, push, ws helpers
  foundations/         # quantity, provenance, io
  realtime/            # webrtc / media
  bridge_meta/         # bridge contracts
  ops_dx/              # audit, CLI, observability
  wire/ asgi/ bridges/ components/ agents/ mcp/ workplace/ …
  PACKAGE_MAP.json     # module → package inventory
```

**There are no top-level `ux_channel/foo.py` aliases.**  
If a module moved, you import the package path.

## Import flow (cognitive)

```text
App code     →  ux_channel.day1  or  ux_channel (public symbols)
Extensions   →  ux_channel.host.* / protocol.* / paint.* / …
Shared law   →  CapService.mint/verify  (same as Rust)
```

```python
# Apps
from ux_channel.day1 import Channel, Region, CapService, state

# Library / power
from ux_channel.host.regions import RegionBook
from ux_channel.protocol.capability import CapService
from ux_channel.paint.morph_ir import elem
```

## Change process

1. Put code in the correct package (see PACKAGE_MAP / package_docs).  
2. `python3 scripts/sync_python_layout.py` (refreshes package `__init__` + catalog).  
3. `python3 scripts/sync_python_layout.py --check` must pass (CI).  
4. Export new public symbols only via root `__init__` + `day1` if they are day-1.  
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
