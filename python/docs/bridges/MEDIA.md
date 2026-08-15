<!-- pyramid -->
Read [../../../START_HERE.md](../../../START_HERE.md) first if you are new. This is Layer 2 (encyclopedia), not the intro.

# Media bridge (`ch.media`) — mesh + LiveKit SFU

**DX dream, no bloat:** one façade, battle-tested clients, host-owned UI.

```python
p = ch.media.plugin("lobby", sub=user_id)  # auto: sfu if configured else mesh
```

## Modes

| Mode | Transport | Client |
|------|-----------|--------|
| **mesh** | uxchannel `/rtc` | `ux-webrtc.js` |
| **sfu** | LiveKit (default adapter) | **`livekit-client`** (npm/CDN) |
| **auto** | sfu if `sfu_provider` set else mesh | — |

## LiveKit production

```python
cfg = ChannelConfig.production(secret)
cfg = replace(cfg,
    sfu_provider="livekit",
    sfu_url=os.environ["LIVEKIT_URL"],
    sfu_api_key=os.environ["LIVEKIT_API_KEY"],
    sfu_api_secret=os.environ["LIVEKIT_API_SECRET"],
)
ch = Channel.boot(app, config=cfg)

p = ch.media.plugin(room_id, sub=user.id, mode="sfu")
# place p.scripts_html + join via UidMedia / livekit-client
```

Or bundle yourself:

```bash
npm i livekit-client
```

```js
import { Room } from "livekit-client";
const { url, token } = JSON.parse(document.getElementById("ux-media-client").textContent);
const room = new Room();
await room.connect(url, token);
```

`cdn=False` on `plugin()` skips jsDelivr tags.

## Mesh (1:1 / tiny groups)

```python
p = ch.media.plugin("lobby", sub=user_id, mode="mesh")
# same bag as ch.webrtc.plugin + data-channel-media-mode=mesh
```

Need **TURN** for real NATs (`ch.webrtc.ice` / env secrets).

## Boundary

| Layer | Owner |
|-------|--------|
| Authz / caps / morph | uxchannel |
| Token + placement bag | `ch.media` |
| Media bytes | LiveKit SFU or browser mesh |
| UI chrome | host (ux_dom, etc.) |

## Application

`ch.media.plugin` · `session` · `mesh` · `sfu` · `mode` · `ice` · `diagnose`

See [STANDARDS.md](../production/STANDARDS.md) · [WEBRTC_DX.md](../webrtc/WEBRTC_DX.md).

## Security (`POST /ux-channel/sfu/token`)

Token mint is **gated** like mesh RTC:

* origin when ``webrtc_require_origin``
* room ticket when ``webrtc_require_ticket`` (or ``sfu_require_ticket``)
* rate limit (shared RTC limiter)
* production rejects empty / ``anon`` identity
* ticket ``sub`` must match ``identity`` when bound

Prefer **server-side** ``ch.media.plugin(..., mode="sfu")`` after your own auth;
HTTP mint is for thin clients that already hold a room ticket.
