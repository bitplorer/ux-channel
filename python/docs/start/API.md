<!-- pyramid -->
Read [../../../START_HERE.md](../../../START_HERE.md) first if you are new. This is Layer 2 (encyclopedia), not the intro.

# API surface — uxchannel 0.1

## Core import (stable)

```python
from ux_channel import (
    Channel, ChannelConfig, Region, Result, Intent,
    ActionRegistry, Principal, ControlAttrs,
    morph, toast, navigate, http_status_for,
    agents, state, attach_audit,
)
```

Optional layers — import from submodules (`ux_channel.quantity`, `ux_channel.bridge_api`,
`.components`, `.push`, `.agents`, …). See [COURSE.md](COURSE.md) · [LAYERS.md](LAYERS.md).

# API reference — uxchannel 0.1

Public surface for application code. Internals (`RegionBook.command`, registry prep) are not app API.

## Package

```python
from ux_channel import (
    Channel,
    ChannelConfig,
    Region,
    Principal,
    Result,
    Intent,
    MemoryStateStore,
    StateConflict,
    __version__,  # "0.1.0"
)
```

Optional:

```python
from ux_channel.asgi.fastapi import mount_channel
from ux_channel.asgi.starlette import mount_channel_starlette
from ux_channel.host.factory import create_channel
from ux_channel.protocol.ops import morph, toast, navigate
from ux_channel.bridge.bridge_api import mount_html  # npm bridge host element only
from ux_channel.foundations.quantity import Quantity
```

## Agents (AX)

```python
from ux_channel import agents

ag = agents(ch)
tools = ag.tools_for()
r = ag.dispatch("inc", {})
print(ag.effects(r).to_dict())
```

Peer dispatch implementation: `ux_channel.agent_runtime.peer` (**internal** — prefer `agents(ch).dispatch`).

## Channel

### Lifecycle

| API | Role |
|-----|------|
| `Channel.boot(app, config=…, secret=…, host="fastapi")` | Registry + mount + façade |
| `Channel.from_registry(reg)` | Wrap existing registry |
| `ch.diagnose()` | Health snapshot (no secrets) |
| `ch.path` | Mount prefix (`/ux-channel`) |
| `ch.registry` | Underlying `ActionRegistry` |

### Regions & actions

| API | Role |
|-----|------|
| `@ch.region` / `@ch.on` | Morph slot / action |
| `ch.control` | Signed control attrs |
| `ch.done` / `ch.fail` | Result verbs |
