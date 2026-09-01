# Layers — open this before the rest of the package

One page. A principal engineer should be able to navigate this tree in minutes.

```text
Intent {action, args, cap}  →  verify  →  action  →  Result {ok, ops[]}
```

That loop is the product. Everything else is a door or a plane.

| Open this | When | Do not start here |
|-----------|------|-------------------|
| `protocol/` | Wire law: Intent, Result, CapService, ops | — |
| `host/` | Channel, Registry, Region, config | — |
| `security/` | CSRF, caps policy, limits | Redis backends (`redis_extra`) |
| `render/` | Morph IR + safe attrs | HTML kits (`components/`) |
| `asgi/` | HTTP mount (FastAPI / Starlette) | Treating FastAPI as the protocol |
| `wire/` | JSON floor + CXB | — |
| `realtime/` | WebRTC / media | Boot / `@ch.on` |
| `bridge/` `bridges/` | Widget islands | Boot / `@ch.on` |
| `agent_runtime/` `mcp/` `workplace/` | Non-human callers | Boot / `@ch.on` |
| `components/` | Optional Channel UI kit | Product UI (use ux-dom) |
| `devtools/` `scaffold/` | CLI / doctor / create-app | Runtime path |

## What Channel.boot always attaches (L2)

Regions, flow, live, document helpers, enterprise mint policy, arch hooks.

## What Channel.boot does **not** attach until you touch it (L4)

| Attribute | Package | First access |
|-----------|---------|--------------|
| `ch.webrtc` | `realtime.webrtc` | `ch.webrtc` / `diagnose()` |
| `ch.media` | `realtime.media` | `ch.media` |
| `ch.bridge` | `bridge.bridge_plane` | `ch.bridge` |

Public names are unchanged. `ch.media.plugin(...)` still works.

`host/factory.py` loads Door D `bridge.plugins` (PluginHub). That is the
extension registry, not the L4 plane façade. `bridge/__init__.py` is lazy
so the hub import does not pull `bridge_plane`.

## FastAPI

`asgi/` is Door F — a host adapter. The protocol does not need HTTP:

```python
from ux_channel import Channel, ChannelConfig, Intent

ch = Channel.boot(config=ChannelConfig.development(secret="dev-" + "x" * 32))

@ch.on
def ping():
    return ch.done()

ch.registry.dispatch(Intent(action="ping", args={}))
```

HTTP later: `Channel.boot(app, host="fastapi")` or `from ux_channel.asgi import mount_channel`.

## Dependents (ux-compose tree)

Compose may import only:

- `from ux_channel import Channel, ChannelConfig`
- `from ux_channel.cek.host_adapter import apply_host_adapter`
- `from ux_channel.protocol.types import Intent`

Do not rename those. Isolation Law lives in compose `wire/`.

## Law vs moving

Frozen: Intent / Result / Cap mint-verify / `Channel.boot` / `@on` / `control` / `done`/`fail`.
Moving: dashboard, presets, scaffold templates, demo HTML.
