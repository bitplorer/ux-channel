<!-- pyramid -->
Read [../../../START_HERE.md](../../../START_HERE.md) first if you are new. This is Layer 2 (encyclopedia), not the intro.

# WebRTC signaling protocols (and ux-channel)

## Standards (what must be exchanged)

WebRTC is **signaling-agnostic**. Browsers require:

| Kind | Payload | Purpose |
|------|---------|---------|
| **offer** | SDP (`RTCSessionDescriptionInit`) | Capabilities / media lines |
| **answer** | SDP | Accept subset |
| **ice** | `RTCIceCandidateInit` | Trickle ICE candidate |
| **ice-done** | `null` | End-of-candidates (optional but useful) |

Specs: SDP, JSEP, ICE ([RFC 8445](https://datatracker.ietf.org/doc/html/rfc8445)), Trickle ICE ([RFC 8838](https://datatracker.ietf.org/doc/rfc8838/)).

There is **no single required transport** (not WS-only, not SIP-only).

## Transports in the wild

| Transport | Use |
|-----------|-----|
| WebSocket | Low-latency trickle (most apps) |
| HTTP poll / long-poll | Simple, firewall-friendly |
| SSE + POST | Push inbox |
| SIP / XMPP Jingle | Telco / federation |
| WHIP / WHEP | Publish/play to **media servers** (SFU/CDN), not mesh chat |

## uxchannel protocol

```text
GET  /ux-channel/rtc?room&peer&name&since[&ticket]   → roster + signals
POST /ux-channel/rtc  {op:signal|leave, kind, payload, ticket?}
WS   /ux-channel/rtc/ws?room&peer&name[&ticket]      → push signals + roster
```

**Kinds:** `offer` | `answer` | `ice` | `ice-done`

**Client preference:** WebSocket first; HTTP poll fallback.

**Auth (optional):**

```python
cfg = ChannelConfig.production(secret, webrtc_require_ticket=True, webrtc_require_origin=True)
ticket = ch.webrtc.sign_ticket("lobby", sub=user_id)
# pass ?ticket= or X-Channel-Rtc-Ticket / data-channel-webrtc-ticket
```

**TURN / ICE:**

```bash
export UX_CHANNEL_TURN_URLS=turn:turn.example.com:3478
export UX_CHANNEL_TURN_USER=u
export UX_CHANNEL_TURN_PASS=p
```

Or `ChannelConfig(webrtc_ice_servers=(...))` / client `iceServers` option.

## Not WHIP

uxchannel mesh signaling is **not** WHIP/WHEP. For broadcast ingest into an SFU, add a separate WHIP endpoint later.

## Related docs

* [WEBRTC.md](WEBRTC.md) — client A/V API  
* [WEBSOCKET.md](../asgi/WEBSOCKET.md) — **ops** WS (`/ux-channel/ws`), different plane

See also [NEXT_STEPS.md](../production/NEXT_STEPS.md).

## Security hardening (0.1)

| Control | Config / behavior |
|---------|-------------------|
| Ticket | `webrtc_require_ticket` (on in `production()`) |
| Origin | `webrtc_require_origin` (on in `production()`) |
| Rate | `webrtc_rate_per_minute` / `webrtc_rate_burst` → HTTP **429** |
| Peer id | sanitize `[A-Za-z0-9._-]{1,64}`; optional `webrtc_min_peer_len` |
| Payload | max 32 KiB per signal |
| Room size | `webrtc_max_peers` |
| ICE in HTML | **STUN only** via `public_ice_servers()` — never embed TURN passwords |
| Store | fingerprint rebuild when max_peers/redis/TTL change |

```python
cfg = ChannelConfig.production(secret, webrtc_min_peer_len=4)
ticket = ch.webrtc.sign_ticket(room, sub=user_id)
```

Standards matrix: [STANDARDS.md](../production/STANDARDS.md) (JSEP/ICE/HTTP SoC).
