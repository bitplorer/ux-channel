# Python layout — packages only (no shims)

See [STABILITY.md](STABILITY.md) for rules.

```text
App  →  day1/  or  root __init__ exports
         │
         ▼
 protocol/   host/   paint/   security/   transport/   …
   Cap*       Channel  morph    CSRF        batch
   Intent     Region   HTML     limits      push
   ops        state
```

| Package | Intent |
|---------|--------|
| `day1` | App imports |
| `protocol` | IR + caps (Rust-parity) |
| `host` | Channel, regions, actions, state |
| `paint` | Morph / HTML |
| `security` | Auth doors / limits |
| `transport` | Streaming helpers |
| `foundations` | Quantity / provenance / io |
| `realtime` | WebRTC |
| `bridge` | Bridge contracts |
| `devtools` | DX / audit / CLI |
| `wire` `asgi` `bridges` … | Product planes |

```python
from ux_channel.api import Channel, Region
from ux_channel.host.regions import RegionBook
from ux_channel.protocol.capability import CapService
```

`PACKAGE_MAP.json` lists every implementation module.  
`scripts/sync_python_layout.py --check` forbids top-level alias modules.
