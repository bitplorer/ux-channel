<!-- pyramid -->
Read [../../../START_HERE.md](../../../START_HERE.md) first if you are new. This is Layer 2 (encyclopedia), not the intro.

# FastAPI integration — uxchannel 0.1

## Install

```bash
pip install "ux-channel[fastapi]"
# or editable: pip install -e ".[fastapi,dev]"
```

## Bootstrap (recommended)

```python
from fastapi import FastAPI
from ux_channel import Channel, ChannelConfig

app = FastAPI()
ch = Channel.boot(
    app,
    config=ChannelConfig.development(secret="…", allow_memory_stores=True),
)
# production:
# ch = Channel.boot(app, config=ChannelConfig.production(secret=os.environ["UX_CHANNEL_SECRET"]))
```

`Channel.boot` creates the registry, mounts the HTTP surface, and returns the `Channel` façade.

### Lower-level (same mount)

```python
from ux_channel import ActionRegistry
from ux_channel.host.config import ChannelConfig
from ux_channel.asgi.fastapi import mount_channel

cfg = ChannelConfig.from_env()
reg = ActionRegistry.from_config(cfg)
mount_channel(app, reg, config=cfg)
```

### Factory

```python
from ux_channel.host.factory import create_channel
reg, hub = create_channel(config=cfg, app=app, host="fastapi")
```

## HTTP surface (default path `/ux-channel`)

| Method | Path | Purpose |
|--------|------|---------|
| **POST** | `/ux-channel/action` | Intent → Result (`application/ux-channel+json` or JSON) |
| **POST** | `/ux-channel/batch` | Batch intents |
| **GET** | `/ux-channel/health` | Liveness |
| **GET** | `/ux-channel/ready` | Readiness |
| **GET** | `/ux-channel/version` | Library / protocol info |
| **GET** | `/ux-channel/static/*` | Client JS (`ux-channel.js`, bridge, inspector) |
| **GET** | `/ux-channel/catalog` | Action catalog (when enabled) |
| **GET** | `/ux-channel/metrics` | Prometheus (if configured) |
| **GET** | `/ux-channel/push/{topic}` | SSE push |
| **GET/POST** | `/ux-channel/trace*` | Inspector (token in production) |

Change prefix with `ChannelConfig(path="/ux-channel")` or `Channel.boot(..., path=...)`.

**Action URL is always** `{path}/action` — e.g. `/ux-channel/action`, not bare `/ux-channel`.

## HTML shell

```python
@app.get("/", response_class=HTMLResponse)
def index():
    return f"""<!doctype html>
<html>
<head>
  {ch.scripts()}
</head>
<body {ch.body_attr_string()}>
  {ch.html(my_region)}
  <!-- controls: ch.control(...).as_dict() → HTML attributes -->
</body>
</html>"""
```

`ch.body_attr_string()` sets at least:

- `data-channel-endpoint="/ux-channel/action"`
- dev flags when in development (`data-channel-dev`, inspector)

## Browser security

Production JSON POSTs require:

| Check | Config |
|-------|--------|
| Custom header `X-UID-Channel: 1` | `require_channel_header=True` (prod default) |
| Origin allowlist / same-origin | `allowed_origins` / `enforce_same_origin` |
| Capability token on mutating actions | `require_cap=True` |

The shipped client (`ux-channel.js`) sends the channel header automatically.

## Auth with FastAPI

Pass a principal into dispatch (middleware / dependency sets it via host `bind_request` + auth resolver, or tests use):

```python
from ux_channel import Principal

# in tests / custom host:
result = ch.registry.dispatch(intent, principal=Principal.of("user-1", roles=["admin"]))
```

```python
@ch.on(name="Admin.x", auth=True, roles=["admin"])
def admin_only():
    return ch.done()
```

`auth=True` reads the principal from the dispatch ContextVar (no need for a `principal` parameter on the handler).

## Starlette

```python
from ux_channel.asgi.starlette import mount_channel_starlette
mount_channel_starlette(app, reg, config=cfg)
```

Same security knobs as FastAPI.

## See also

[HOW_TO.md](../start/HOW_TO.md) · [PRODUCTION.md](../production/PRODUCTION.md) · [SECURITY_AUDIT.md](../security/SECURITY_AUDIT.md)

## Live SSE push

```python
ch.body_attr_string(push_topic="live.board")
# GET /ux-channel/push/live.board — EventSource auto-wired by ux-channel.js
```

See [SSE.md](SSE.md) and `examples/sse_live_ticker/`.

## WebSocket

| | |
|--|--|
| **WS** | `/ux-channel/ws` |
| Query | `token`, `ticket`, `topics` |
| Docs | [WEBSOCKET.md](WEBSOCKET.md) |
