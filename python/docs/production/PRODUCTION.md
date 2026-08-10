# Production — ux-channel 0.1

### Brand lines

| Layer | Name |
|-------|------|
| **PyPI / pip** | `ux-channel` |
| **Import** | `ux_channel` |
| **CLI** | **`uxchannel`** |

Companion document stack: [STACK.md](../start/STACK.md) · checklist: [PRODUCTION_CHECKLIST.md](PRODUCTION_CHECKLIST.md)

## Checklist

- [ ] Secret ≥ 32 random chars via `UX_CHANNEL_SECRET`
- [ ] `ChannelConfig.production(secret=…)` or `ChannelConfig.from_env()`
- [ ] `require_cap=True`, `require_channel_header=True` (production defaults)
- [ ] HTTPS at the edge
- [ ] Escape all user strings in region HTML
- [ ] Multi-worker: Redis (`REDIS_URL` / `with_redis`) — never memory stores across workers
- [ ] `allowed_origins` if browser Origin ≠ Host
- [ ] Never `trusted_proxy=True` without edge XFF rewrite
- [ ] Probes: `GET /ux-channel/health`, `GET /ux-channel/ready`
- [ ] Trace off or token-gated; `observe=otel` only with exporter owned by the app
- [ ] Full security notes: [SECURITY_AUDIT.md](../security/SECURITY_AUDIT.md)

## Bootstrap

```python
import os
from fastapi import FastAPI
from ux_channel import Channel, ChannelConfig

app = FastAPI()
ch = Channel.boot(
    app,
    config=ChannelConfig.production(secret=os.environ["UX_CHANNEL_SECRET"]),
)
```

Or environment-driven:

```python
cfg = ChannelConfig.from_env()  # UX_CHANNEL_*
ch = Channel.boot(app, config=cfg)
```

## Environment variables

| Variable | Meaning |
|----------|---------|
| `UX_CHANNEL_SECRET` | **Required** HMAC secret (≥32) |
| `UX_CHANNEL_ENV` | `production` / `development` |
| `UX_CHANNEL_PATH` | Control-plane mount (default **`/ux-channel`**; not `/_uid`) |
| `UX_CHANNEL_MAX_REQUEST_BYTES` | Body cap |
| `UX_CHANNEL_ACTION_TIMEOUT_S` | Handler timeout |
| `UX_CHANNEL_RATE_LIMIT_PER_MINUTE` | Rate limit |
| `UX_CHANNEL_ALLOWED_ORIGINS` | Comma-separated origins |
| `UX_CHANNEL_HEALTH_LIST_ACTIONS` | List action names on /health (avoid public prod) |
| `UX_CHANNEL_PUSH_TOKEN` | Shared SSE secret |
| `UX_CHANNEL_PUSH_REQUIRE_AUTH` | Fail-closed SSE (default on in production) |
| `UX_CHANNEL_OBSERVE` | `off` \| `dev` \| `otel` |
| `UX_CHANNEL_MIN_CLIENT_VERSION` | Optional client gate |

## Scaling

| Concern | Single worker | Multi worker |
|---------|---------------|--------------|
| Caps | Stateless HMAC | Same secret on all pods |
| Once / idempotency / rate | Memory OK for dev | **Redis** |
| Draft / state | Memory | Redis / DB |
| Static JS | `/ux-channel/static` | CDN optional; **one package copy** |

## Client body

```html
<body data-channel-endpoint="/ux-channel/action">
```

Prefer `ch.body_attr_string()` / `ch.scripts()`.

## With ux-dom

```python
from ux_dom import Document
from ux_dom.runtime import XElement, Htmx, Csp, Channel as ChannelScripts

document = Document(...).use(XElement(), Htmx(), Csp.auto(), ChannelScripts.optional())
# ChannelScripts is UxChannelRuntime — tags only; Channel.boot still owns /ux-channel
```

See [STACK.md](../start/STACK.md). CSRF: host meta optional; **`X-Channel: 1` always**.

## Ops probes

| Path | Role |
|------|------|
| `GET /ux-channel/health` | Liveness |
| `GET /ux-channel/ready` | Readiness (stores) |
| `uxchannel doctor` | DX snapshot |
| `uxchannel dashboard` | Operator model (observe-only) |
