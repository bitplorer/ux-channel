# WebRTC security (ux-channel)

Practical checklist + answers to **DTLS certificate pinning**, **simulcast**, and
**API shape**.

## Best practices (mapped to this library)

| Practice | uxchannel |
|----------|-------------|
| Authenticate room join | `webrtc_require_ticket` + `ch.webrtc.sign_ticket(room, sub=…)` |
| CSRF / cross-site | `webrtc_require_origin=True` (`production()` default) |
| Rate-limit signaling | `webrtc_rate_per_minute` / `webrtc_rate_burst` → HTTP 429 |
| Cap room size / payload | `webrtc_max_peers`, 32 KiB signal cap |
| Sanitize ids | room/peer `[A-Za-z0-9._-]{1,64}` |
| No secrets in HTML | `ice.html()` only in data-*; TURN only via `ice.live` / `ice.url` |
| HTTPS | required for `getUserMedia` / secure WebSocket |
| Multi-worker store | Redis RTC when `redis_url` set |
| Treat DC peers as hostile | validate JSON; size-limit; no secrets on data channel |
| IP privacy (optional) | client `iceTransportPolicy: "relay"` + your TURN |

```python
cfg = ChannelConfig.production(os.environ["UX_CHANNEL_SECRET"])
ch = Channel.boot(app, config=cfg)
ticket = ch.webrtc.sign_ticket("lobby", sub=user_id)
# body: ch.body_attr_string(webrtc="lobby") + ticket attr
```

`ch.webrtc.diagnose()` returns a **security posture** summary (no secrets).

---

## DTLS certificate pinning

### Reality (browsers)

**Web apps cannot pin DTLS certificates for `RTCPeerConnection`.**

- There is **no** standard JS API to pin peer (or SFU) DTLS cert fingerprints for WebRTC media.
- Media/data are already encrypted with **DTLS-SRTP / DTLS-SCTP** between endpoints.
- Trust model is: **authenticated signaling** decides *who* you call; DTLS protects *the pipe*.

### What to do instead

| Goal | Approach |
|------|----------|
| Trust the **site** | HTTPS + HSTS; pin **signaling** TLS at the network edge if required (not WebRTC DTLS) |
| Trust the **room** | HMAC tickets (`sign_ticket`), origin checks, rate limits |
| Trust **media server** | SFU over HTTPS/WSS; server TLS certs managed ops-side; WHIP/WHEP auth |
| Hide IPs | `iceTransportPolicy: "relay"` + short-lived TURN credentials |
| Enterprise lock-down | MDM / browser policy — outside web app code |

### Client API

```js
UxWebRTC.securityNotes();
// { dtlsPinning: false, dtlsPinningReason: "…", recommendations: […] }
```

### Non-goal

Implementing fake “DTLS pinning” in JS would be **security theater**. We document the gap and harden the planes we control (signaling + ICE policy + tickets).

---

## Simulcast optimization

### Client (mesh / SFU-bound)

```js
const room = await UxWebRTC.join({
  room: "call",
  rtcPath: "/ux-channel/rtc",
  simulcast: true,           // 3 layers q/h/f on video senders
  iceTransportPolicy: "all", // or "relay"
  media: { audio: true, video: true },
});

// Adaptive layers (when encodings exist)
await room.setSimulcastLayers({ q: true, h: true, f: false }); // drop full layer
await room.setVideoBitrate(800);  // cap kbps on encodings
await room.setEncodingActive(true);
```

Layers (default when `simulcast: true`):

| rid | scale | maxBitrate |
|-----|-------|------------|
| `q` | 4× down | 150 kbps |
| `h` | 2× down | 500 kbps |
| `f` | 1× | 1.5 Mbps |

### Server

uxchannel mesh **signaling does not select layers** — that is the browser (mesh) or an **SFU** (`ux_channel.sfu`). For large calls, publish with simulcast to LiveKit/etc.; mesh stays small-room.

---

## Public API pattern (ux-channel)

**Day-1 (only):**

```text
ch.webrtc.enabled | path | ws_path | sign_ticket | body_attrs | diagnose
```

**Power / HTML-safe ICE:**

```text
ch.webrtc.public_ice_servers()   # embed in HTML
ch.webrtc.default_ice_servers()  # server-side (may include TURN from env)
ch.webrtc.store()                # tests / hosts
```

**Layers (explicit import):**

```python
from ux_channel.realtime.sfu import LiveKitSfu
from ux_channel.realtime.whip import ...
```

Never put free `sign_rtc_ticket` on `uxchannel` root for product apps — use `ch.webrtc`.

```python
print(Channel.describe())
# Day-1 includes webrtc plane; layers stay submodules
```

---

## Related

* [WEBRTC_SIGNALING.md](WEBRTC_SIGNALING.md) — offer/answer/ice protocol  
* [WEBRTC.md](WEBRTC.md) — client A/V + data channel  
* [API_SURFACE.md](../start/API_SURFACE.md) — root vs layer rules

## Short-lived TURN (0.1.x)

Prefer coturn **static-auth-secret**:

```bash
export UX_CHANNEL_TURN_URLS=turn:turn.example.com:3478
export UX_CHANNEL_TURN_SECRET=your-static-auth-secret
export UX_CHANNEL_TURN_TTL=300
```

* HTML / `public_ice_servers` / `data-channel-webrtc-ice` → **STUN only**
* `GET /ux-channel/rtc/ice?room=&ticket=` → STUN + time-bound TURN (same auth as poll)
* Client `UxWebRTC.join({ iceUrl, ticket })` refreshes ICE before connect

## ICE rule (DX)

```text
ch.webrtc.ice.html()  →  embed anywhere
ch.webrtc.ice.live()  →  server / GET ice.url only
ch.webrtc.plugin()    →  wires both automatically
```
