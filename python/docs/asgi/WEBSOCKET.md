# WebSocket — uxchannel 0.1

Duplex channel for **live Results** (same bus as SSE) and optional **Intent** dispatch.

**Endpoint:** `WS {path}/ws` (default `/ux-channel/ws`)  
**Library version:** 0.1.0

---

## When to use WS vs SSE

| | SSE `GET /push/{topic}` | WebSocket `/ws` |
|--|-------------------------|-----------------|
| Direction | Server → client | Bidirectional |
| Subscribe | One topic per connection | Many topics per connection |
| Actions | Separate `POST /action` | Optional `type:intent` (caps still required) |
| Browser API | `EventSource` | `WebSocket` |
| Auth | ticket / token / public.* | **Same policy** + Origin check |

Prefer **SSE** for simple live boards. Prefer **WS** when you need multi-topic subscribe or low-latency duplex.

---

## Security (production)

Same doors as SSE where applicable:

| Control | Behavior |
|---------|----------|
| `push_require_auth` | Production fail-closed on connect without ticket/token/public topics |
| `push_token` | When set, required for private connect/subscribe |
| **Tickets** | `ch.sign_push` / `ch.sign_ws` (identical HMAC) |
| **Public prefixes** | `public.*` open when `push_allow_public` |
| **Origin** | `allowed_origins` / `enforce_same_origin` via `check_ws_origin` |
| **Actions** | Caps still verified; `ws_allow_actions=False` disables Intent over WS |
| **Limits** | `ws_max_subscriptions`, `ws_max_message_bytes` |
| **`ws_enabled=False`** | Close with 1008 |

### Connect policy

1. Reject if `ws_enabled` is false  
2. Check **Origin**  
3. `authorize_ws_connect` — ticket / token / initial public topics / fail-closed  
4. `accept` → `hello`  
5. Each `subscribe` re-runs **topic** authorize (SSE-equivalent)

### Bottom line

- **WS is not a bypass for caps.** Mutations still need signed capabilities.  
- **Private topics need ticket or push_token** (or public prefix).  
- **One ticket works for SSE and WS.**  
- **Escape morph HTML** the same as everywhere else.  
- **Multi-worker:** Redis push bus (same as SSE).

---

## Protocol

### Client → server

```json
{"type":"subscribe","topic":"public.rates"}
{"type":"unsubscribe","topic":"public.rates"}
{"type":"intent","action":"Ping.hi","args":{},"cap":"…"}
{"type":"ping"}
```

### Server → client

```json
{"type":"hello","uid":"1","runtime": "0.1.0"}
{"type":"subscribed","topic":"public.rates"}
{"type":"result","ok":true,"ops":[…],"uid":"1"}
{"type":"error","code":"unauthorized","message":"…"}
{"type":"pong"}
{"type":"ping"}
```

`type:result` is applied with `uxChannel.applyResult` in the browser client.

---

## Server usage

```python
from ux_channel.transport.push import get_push_bus

# Feeder (same as SSE)
get_push_bus().publish("public.rates", ch.refresh(ticker))

# Private page
ticket = ch.sign_ws("shop.lobby", sub=user_id)
# body:
ch.body_attr_string(ws=True, push_topic="shop.lobby", push_ticket=ticket)
```

### Config / env

| Knob | Env | Default |
|------|-----|---------|
| `ws_enabled` | `UX_CHANNEL_WS_ENABLED` | true |
| `ws_allow_actions` | `UX_CHANNEL_WS_ALLOW_ACTIONS` | true |
| `ws_require_origin` | `UX_CHANNEL_WS_REQUIRE_ORIGIN` | false |
| `ws_max_subscriptions` | `UX_CHANNEL_WS_MAX_SUBSCRIPTIONS` | 16 |
| `ws_max_message_bytes` | `UX_CHANNEL_WS_MAX_MESSAGE_BYTES` | 256000 |
| Shared with SSE | `UX_CHANNEL_PUSH_TOKEN`, ticket max age, public prefixes | |

---

## Client

Declarative:

```html
<body data-channel-ws="/ux-channel/ws"
      data-channel-push-topic="public.live"
      data-channel-push-ticket="…">
```

```js
const h = uxChannel.subscribeWs();
h.subscribe("public.other");
h.send({ type: "intent", action: "X.y", args: {}, cap: "…" });
```

---

## Tests

`tests/webrtc/test_websocket_security.py` — connect deny, public/ticket/token, intent+cap, origin, limits.

---

## Related

[SSE.md](SSE.md) · [SECURITY_AUDIT.md](../security/SECURITY_AUDIT.md) · [FASTAPI.md](FASTAPI.md) · [PRODUCTION.md](../production/PRODUCTION.md)

## Morph stability (client)

Region refresh fragments may omit `data-channel-id` on the root. The client **copies**
the existing element's `data-channel-id` before `replaceWith` so repeated push Results
keep finding `[data-channel-id="…"]`. Server-side `ch.multi` also wraps missing ids.

If you open both SSE and WebSocket, only WebSocket auto-connects when `data-channel-ws`
is present (avoids double apply). Use `uxChannel.onWsMessage(fn)` for page chrome
without a second socket.

Demo: `examples/ws_live_board/`


## Live refresh reliability

- Push bus fan-out uses drop-oldest on full queues (same as SSE).
- Client resubscribes tracked topics on reconnect/open.
- `type:"result"` envelopes are applied via `applyResult` (same as HTTP/SSE).
- `type:"error"` and transport failures emit `uid:error` / `uid:wsError`.
- Failed `render_error` Results still deliver to subscribers (clients toast error).
