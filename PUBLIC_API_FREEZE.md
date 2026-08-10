# Public API freeze — ux-channel 0.1

Application authors and peer implementers may rely on this surface.
Everything else is internal or power and may change without a major bump.

## Application imports (frozen)

```python
from ux_channel import (
    Channel,
    ChannelConfig,
    Region,
    CapService,
    CapError,
    Intent,
    Result,
    ErrorObject,
    state,
    agents,
    attach_audit,
    morph,
    toast,
    navigate,
    signal_set,
)
# same objects:
from ux_channel.api import Channel, Region, CapService, state
```

| API | Role |
|-----|------|
| `Channel.boot` | Attach channel to app |
| `@ch.region` / `@ch.on` | Region paint + action |
| `ch.control(...)` | Control attrs (+ cap mint) |
| `ch.done` / `ch.fail` | Result verbs |
| `ch.runtime` | Placement data (not HTML ownership) |
| `ch.mint` | Cap mint (Rust-parity name) |
| `ch.media` / `ch.bridge` | Optional planes |
| `ch.diagnose()` / `ch.doctor()` | Health |
| `Channel.describe()` / `Channel.help()` | Progressive docs |
| `state(ch)` | Session / client / db guards |
| `agents(ch)` | Agent façade |
| `attach_audit(ch)` | Intent log / forensics |

**You own HTML.** Channel owns control, trust, regions, ops, placement **data**.

## Wire + caps (frozen, dual-language)

```python
from ux_channel.protocol import CapService, CapError, Intent, Result, morph, toast
from ux_channel.wire import encode, decode, dumps, loads, configure_wire, encode_cxb, decode_cxb
```

| API | Role |
|-----|------|
| `CapService.mint` / `verify` / `hash_args` | Capability (sorted JSON hash) |
| Op builders | `morph`, `toast`, `navigate`, `signal_set`, … |
| Wire codecs | JSON floor; CXB upgrade |

Rust peer: same cap algorithm + CXB decode vs `conformance/`.

## Host construction (frozen)

- `Channel.boot(app, config=...)`
- `ChannelConfig.development` / `.production` / `.from_env`
- Env prefix **`UX_CHANNEL_`**
- Stores: `from ux_channel.host.stores import MemoryStateStore` (power)

## Power packages (stable entry, evolving interior)

| Package | Entry |
|---------|--------|
| `host` | `Channel`, `Region`, `RegionBook` |
| `protocol` | caps + IR |
| `render` | morph / HTML helpers |
| `security` | `intent_headers`, `attenuate` |
| `asgi` | `mount_channel` |
| `realtime` | WebRTC / media |
| `bridge` / `bridges` | widgets |
| `devtools` | audit / CLI |
| `foundations` | Quantity |
| `workplace` / `agent_runtime` / `mcp` | product planes |

## Explicitly not frozen on root

- Demo HTML helpers (`render.kit`)
- Redis backends (`redis_extra`)
- Internal registry / factory details
- Dashboard plugins, profiling internals

## Change policy

1. Renames on this list → major or explicit deprecation.
2. Layout: [python/STABILITY.md](python/STABILITY.md).
3. Model: [MENTAL_MODEL.md](MENTAL_MODEL.md).
4. Gate: `python/tests/gate/` + `make verify`.


## Star-import vs attribute import

* ``from ux_channel import *`` only pulls ``__all__`` (application + stable core).
* ``from ux_channel import MemoryStateStore`` still works (power re-export bound on root).
* Prefer power packages for new code: ``host.stores``, ``host.ssr_state``, etc.
