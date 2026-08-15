<!-- pyramid -->
Read [../../../START_HERE.md](../../../START_HERE.md) first if you are new. This is Layer 2 (encyclopedia), not the intro.

> **Media-first (application):** prefer ``ch.media.plugin(room, sub=…)`` (``mode='mesh'|'sfu'|'auto'``). ``ch.webrtc`` remains the mesh power plane.

# WebRTC DX — plugin + ICE (low cognitive load)

## Mission

Channel owns **signaling, tickets, client runtime, ICE placement rules**.  
Hosts own **all UI**.

## Application (two calls)

```python
ch = Channel.boot(app, config=ChannelConfig.production(secret))
p = ch.webrtc.plugin("lobby", sub=user_id)
# place p.scripts_html + p.attr_string; join with p.client
```

That is enough. ICE is **correct by construction**.

---

## ICE — one rule

| Name | What | Where it may appear |
|------|------|---------------------|
| **`ice.html()`** | STUN / credential-free | HTML, `data-channel-webrtc-ice`, `plugin.client.iceServers` |
| **`ice.live(sub=…)`** | STUN + short-lived TURN | Server only, or via **`ice.url`** after ticket |
| **`ice.url`** | `GET …/rtc/ice` | Client fetches with ticket (`plugin.client.iceUrl`) |

```text
html  →  always safe to embed
live  →  never in data-* / SSR HTML
url   →  browser path from html → live
```

**You do not decide where TURN passwords go.** They only exist on the `live` path.

```python
ch.webrtc.ice.html()                 # public
ch.webrtc.ice.live(sub=user_id)      # authenticated mint
ch.webrtc.ice.url                    # "/ux-channel/rtc/ice"
ch.webrtc.ice.posture()              # {mode, urls, …} no secrets
```

Aliases (same thing): `public_ice_servers` ≡ `ice.html`, `ice_servers` ≡ `ice.live`.

### Flexible overrides (power)

```python
# Custom STUN list in config
ChannelConfig(..., webrtc_ice_servers=({"urls": "stun:…"},))

# Env TURN (preferred short-lived)
UX_CHANNEL_TURN_URLS=turn:…
UX_CHANNEL_TURN_SECRET=…          # coturn static-auth-secret
UX_CHANNEL_TURN_TTL=300

# Skip live fetch: pass iceServers yourself (still your responsibility)
ch.webrtc.session("r", iceServers=[...])  # via extra_client kwargs
```

Legacy long-lived `UX_CHANNEL_TURN_USER` / `PASS` still work for `live()` but **never** enter `html()`.

---

## Plugin bag

```python
p = ch.webrtc.plugin("lobby", sub=user_id)
p.scripts_html   # head
p.attr_string    # body (includes ice html + ice-url)
p.client         # iceServers=html, iceUrl=url, ticket, paths
p.client_json    # compact JSON for host script tags
```

Any template engine / DSL only **places** these strings.

---

## Non-goals

* Call-room HTML/CSS/widgets in the library  
* Framework wrappers  
* Putting TURN credentials in `data-channel-webrtc-ice`

See [WEBRTC_SECURITY.md](WEBRTC_SECURITY.md) · [WEBRTC.md](WEBRTC.md).
