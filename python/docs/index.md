<!-- pyramid -->
Read [../../START_HERE.md](../../START_HERE.md) first if you are new. This is Layer 2 (encyclopedia), not the intro.

# uxchannel documentation

**Intent → Action → Result(ops)** for server-driven UI.

## Start here

| Doc | Purpose |
|-----|---------|
| **[FEATURES](FEATURES.md)** | **Complete feature encyclopedia** (API · impl · use cases · tests) |
| [GOLDEN_PATH](start/GOLDEN_PATH.md) | First working app |
| [API_SURFACE](start/API_SURFACE.md) | What is public |
| [LAYERS](start/LAYERS.md) | Where to import |
| [HOW_TO](start/HOW_TO.md) | Recipes |
| [FREEZE_0.1](start/FREEZE_0.1.md) | Frozen application speech |

Repo-level design maps: [ARCHITECTURE](../../ARCHITECTURE.md) · [AUTOMATION](../../AUTOMATION.md) · [LONGEVITY](../../LONGEVITY.md).

## By plane (ontology)

| Package | Topics |
|---------|--------|
| [start/](start/) | Golden path, API, layers, naming, principles |
| [core/](core/) | Result, errors, wire contract |
| [regions/](regions/) | Regions, components, morph paint |
| [state/](state/) | Session / client / SSR state |
| [asgi/](asgi/) | FastAPI, SSE, WebSocket, observability |
| [bridges/](bridges/) | Bridge contracts, plugins, media, NPM |
| [client/](client/) | JS runtime, CSRF, interop |
| [webrtc/](webrtc/) | Signaling, ICE, security |
| [workplace/](workplace/) | Workplace, I/O channel, outbox |
| [agents/](agents/) | AX façade, MCP verticals |
| [foundations/](foundations/) | Quantity, architecture, waves |
| [security/](security/) | Security audit |
| [production/](production/) | Deploy, soak, enterprise, Redis |
| [dx/](dx/) | DX, scaffold, inspector, examples |

## Application imports

```python
from ux_channel import Channel, Region, CapService, state, morph, agents
from ux_channel.api import Channel, CapService, state
from ux_channel.host.stores import MemoryStateStore
from ux_channel.foundations import Quantity
from ux_channel.asgi import mount_channel
from ux_channel.devtools import attach_audit
```

Power layers: import by home (`ux_channel.foundations`, `.workplace`, `.realtime`, …) — never invent root aliases.

Layout identity law: [../STABILITY.md](../STABILITY.md).
