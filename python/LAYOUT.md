# Python package layout — cohesive packages (mature library structure)

> **Goal:** high cohesion, low coupling, cognitive clarity — without losing any 0.x import paths.

## Mental model (read this once)

```text
Apps import day-1 or cohesive packages
        │
        ▼
┌─────────────┐   ┌──────────────┐   ┌─────────────┐
│ protocol    │   │ host         │   │ paint       │  … domain packages
│ types ops   │   │ Channel      │   │ morph html  │
│ capability  │   │ regions      │   │ placement   │
│ wire/       │   │ state        │   │             │
└─────────────┘   └──────────────┘   └─────────────┘
        │                  │
        ▼                  ▼
  shared law w/ Rust    day-1 apps

Legacy: top-level `ux_channel.regions` etc. are **thin shims** → same objects.
```


Intent ↔ name constitution: [`../NAMING.md`](../NAMING.md).

## Region naming (quick)

| Type | Package path | Role |
|------|--------------|------|
| `Region` | `host/region_component.py` | **One** slot — app code |
| `RegionBook` | `host/regions.py` | Registry (`ch.regions`) |
| shims | `region_component.py`, `regions.py` | Legacy imports |

Not a rename: **Region ≠ RegionBook**.

## Preferred imports (new code)

```python
# Day-1 apps
from ux_channel.day1 import Channel, Region, state, agents

# Or by cohesive package
from ux_channel.host.dx import Channel
from ux_channel.host.regions import RegionBook
from ux_channel.protocol.capability import CapabilityService
from ux_channel.protocol.types import Intent, Result
from ux_channel.paint.morph_ir import elem
from ux_channel.security_plane.security import safe_href
```

## Stable legacy imports (never broken in 0.x)

```python
from ux_channel import Channel, Region, Intent, Result
from ux_channel.regions import RegionBook
from ux_channel.capability import CapabilityService
```

These resolve through **compatibility shims** to the cohesive packages.

## Physical tree

```text
python/src/ux_channel/
  __init__.py              # root façade (frozen public exports)
  day1.py → host/day1.py   # shim → day-1 surface
  protocol/                # IR + caps (+ wire/ subpackage)
  host/                    # Channel, regions, registry, state
  paint/                   # HTML, morph, placement
  security_plane/          # auth doors, limits (name avoids shadowing)
  transport/               # batch, push, ws helpers
  foundations/             # quantity, provenance, io
  realtime/                # webrtc, sfu, media
  bridge_meta/             # bridge contracts/scaffold
  ops_dx/                  # audit, CLI, observability
  wire/ asgi/ bridges/     # existing focused subpackages
  components/ agents/ mcp/ workplace/
  zones/                   # navigational catalog
  <module>.py              # LEGACY SHIMS only (thin)
```

## Package responsibilities (cohesion)

| Package | Owns | Must not own |
|---------|------|----------------|
| **protocol** | Intent/Result/ops/errors/caps/encode | HTML, HTTP servers |
| **host** | Channel, regions, actions, state | npm bridges, WebRTC |
| **paint** | Morph IR, HTML safety, placement | Cap crypto |
| **security_plane** | CSRF, attenuate, rate limits | Business actions |
| **transport** | batch/push/ws helpers | Cap algorithms |
| **foundations** | Quantity, provenance, io_channel | UI morph |
| **realtime** | WebRTC/SFU/media | Core Intent path |
| **bridge_meta** | Bridge protocol/scaffold | Region paint |
| **ops_dx** | Audit, CLI, metrics | Wire codecs |
| **wire/** | Codecs + negotiate | Regions |
| **asgi/** | HTTP adapters | Cap implementation |

## Coupling rules

1. **protocol** does not import **host** or **paint**.
2. **host** may import **protocol** and **paint**; not **realtime** or **bridges**.
3. **paint** may import **protocol** (ops); not **asgi**.
4. Optional planes (**realtime**, **mcp**, **workplace**) depend inward, not the reverse.
5. Shims import implementations only — no logic.

## Navigation helpers

```python
from ux_channel.zones import host, protocol, help_all
print(host.help())
print(protocol.MEMBERS)
```

## Tests

| Suite | Path | When |
|-------|------|------|
| Gate (always CI) | `tests/gate/` | `make verify` |
| Full product | `tests/{core,regions,…}` | optional extras |

## See also

- [ONTOLOGY.md](ONTOLOGY.md) — concepts (Region vs Bridge)
- [STRUCTURE.md](STRUCTURE.md) — permanent vs moving
- [MERGE.md](MERGE.md) — release + monorepo merge
