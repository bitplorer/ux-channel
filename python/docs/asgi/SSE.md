# Live SSE push — uxchannel 0.1

Server-initiated **Result** delivery for live tickers and boards **without user clicks**.

**Library version:** 0.1.0

---

## Protocol

| Side | Piece |
|------|--------|
| Server | `PushBus.publish(topic, result)` |
| HTTP | `GET {path}/push/{topic}` → `text/event-stream` |
| Browser | **EventSource** (baked into `ux-channel.js`) → `applyResult` |

Same morph/toast ops as `POST /action`. Only the **trigger** differs (clock/feed vs click).

```text
feeder / worker
    → ch.refresh(...)  or  Result.success / Result.ops(...)
    → PushBus.publish(topic, result)
              ↓
GET /ux-channel/push/{topic}   (SSE)
              ↓
EventSource (ux-channel.js)
    → applyResult → morph / toast / …
```

---

## Declarative client (preferred)

```python
ch.body_attr_string(push_topic="live.board")
# optional: push_token="…", push="/ux-channel/push/live.board"
```

```html
<body
  data-channel-endpoint="/ux-channel/action"
  data-channel-push-topic="live.board">
</body>
```

Comma-separated topics: `data-channel-push-topic="a,b"`.

On load, `ux-channel.js` calls `subscribePush` (EventSource) automatically.

---

## Programmatic client

```js
uxChannel.subscribePush("live.board");
uxChannel.subscribePush({
  topic: "live.board",
  token: "…",
  onApplied(result) { /* optional */ },
});
uxChannel.unsubscribePush("live.board");

document.addEventListener("uid:push", (ev) => {
  console.log(ev.detail.topic, ev.detail.result);
});
```

---

## Server feeder

```python
import asyncio
from ux_channel.transport.push import get_push_bus

async def feeder():
    while True:
        await asyncio.sleep(1.5)
        # update draft / DB …
        result = ch.refresh("live.ticker", "live.status")
        get_push_bus().publish("live.board", result)

# FastAPI lifespan: asyncio.create_task(feeder())
```

Runnable demo: [`examples/sse_live_ticker/`](../examples/sse_live_ticker/).

---

# SSE security issues (0.1)

SSE is **not** protected by the same doors as `POST /action` (caps, CSRF header, per-action auth).  
This section documents **known issues**, **bottom line**, and **solutions** for operators and future library work.

## What the library implements today

| Control | Status in 0.1 |
|---------|----------------|
| Optional shared `push_token` (`UX_CHANNEL_PUSH_TOKEN`) | Yes — Bearer **or** `?token=` |
| **Signed push tickets** (`ch.sign_push` / `?ticket=`) | **Yes** — topic-bound, short TTL |
| **Public topic prefixes** (default `public.*`) | **Yes** — open without creds when `push_allow_public` |
| **`push_require_auth`** fail-closed in production | **Yes** (dev default open) |
| Topic shape validation | **Yes** — rejects path-like / empty / oversized |
| `push_open` break-glass | **Rejected** in production config |
| Auto EventSource + ticket/token attrs | Yes (`data-channel-push-ticket`) |
| Queue backpressure (`maxsize=64`) | Yes |
| Keepalive comments (~15s) | Yes |
| Cap / Intent on subscribe | No (by design — use tickets) |
| CSRF header on SSE | No (GET + EventSource) |
| HTML sanitization of morph payloads | **No** (app must escape) |
| Multi-worker fan-out without Redis | Memory bus is per process — use Redis |

Source: `ux_channel/push_security.py`, `asgi/fastapi.py`, `static/ux-channel.js`.

### Production authorize order

1. Validate topic  
2. `push_open` (dev/break-glass only; forbidden in production config)  
3. Public prefix match → allow  
4. Valid **ticket** for this topic → allow  
5. Valid **push_token** → allow  
6. If `push_token` is **configured** but missing/wrong → **Deny** (even in development)  
7. If `push_require_auth` is false → allow  
8. **Deny 401**

---

## Issue catalog

### 1. Open subscribe by default

**Issue:** If `push_token` is unset, **anyone** who can reach `GET /ux-channel/push/{topic}` receives every Result published on that topic.

**Impact:** Data leak for private boards; scrapers; free load on your workers.

**When OK:** Explicitly public feeds (e.g. display-only bullion rates with no PII).

**Solutions:**

| Layer | Action |
|-------|--------|
| Config | Set `ChannelConfig.push_token` / `UX_CHANNEL_PUSH_TOKEN` for non-public topics |
| Product | Use separate topics: `public.*` vs private; never mix |
| Future lib | Production default-deny unless `push_public_topics` allowlist |

---

### 2. Global token ≠ per-user authorization

**Issue:** One shared `push_token` only proves “knows the secret,” not “may read topic `user:42`.”

**Impact:** IDOR-style subscribe if topics are guessable (`user:1`, `shop:7`).

**Solutions:**

| Approach | Detail |
|----------|--------|
| **Unguessable topics** | Mint `push/{uuid}` after auth; map uuid → audience server-side |
| **Subscribe tickets** (recommended product pattern) | Short-lived HMAC: `topic + sub + exp` verified on connect (app middleware or future `sign_push`) |
| **Edge auth** | API gateway / BFF validates session **before** SSE hits the app |
| **Filter on publish** | Only publish tenant-safe payloads; still hide topics from other tenants |

**Not a solution:** Putting the user id only in the topic string while sharing one global token.

---

### 3. Query-string tokens (EventSource limitation)

**Issue:** Browser `EventSource` cannot set `Authorization` headers. The client therefore uses:

```text
/ux-channel/push/{topic}?token=…
```

(`data-channel-push-token` / `subscribePush({ token })`).

**Impact:**

- Token appears in **access logs**, **proxies**, **browser history**
- Risk of **Referer** leakage to third-party assets if policy is loose

**Solutions:**

| Layer | Action |
|-------|--------|
| Tokens | Prefer **short TTL** tickets, not long-lived master secrets in HTML |
| HTTP | `Referrer-Policy: no-referrer` (or strict-origin) on app pages |
| Ops | Scrub `token=` from access logs |
| Client | Non-browser consumers should use **Bearer** (supported by the route) |
| Future | `fetch` + stream reader if you must avoid query tokens in browsers |

---

### 4. Cross-site EventSource + cookies

**Issue:** A third-party page may open `EventSource` to your origin. Whether cookies are sent depends on **SameSite** and how you authenticate.

**Impact:** If SSE is “cookie session only” with weak SameSite, another site might read the stream.

**Solutions:**

- Session cookies: `SameSite=Lax` or `Strict`, `Secure`, `HttpOnly`
- Require a **non-cookie** secret/ticket on subscribe for private streams
- Do not treat “user has a session cookie” as sufficient without topic ACL

---

### 5. XSS via pushed morph HTML

**Issue:** SSE delivers the same `morph` ops as actions. Channel does **not** sanitize HTML bodies. Unescaped user input in region renderers is applied to **all** subscribers.

**Impact:** Stored/reflected XSS amplified by fan-out.

**Solutions:**

```python
import html as html_lib
# in region render:
html_lib.escape(user_controlled_string)
```

- Treat feeder code with the same escape discipline as request handlers  
- Avoid pushing admin-only HTML on public topics  
- Future lib: optional strict sanitizer policy (see SECURITY_AUDIT)

---

### 6. Dangerous navigate / push_url in pushed Results

**Issue:** A compromised feeder (or bug) could publish `navigate` / `push_url` with bad schemes.

**Mitigation already in library:** href sanitizer strips `javascript:`, `data:`, protocol-relative abuse on encode paths (same as actions).

**Solutions:** Keep sanitizer on; never disable for “convenience”; host allowlists in a later release.

---

### 7. Denial of service (connections & payload size)

**Issue:** Each subscriber holds an async queue and a streaming response. Many clients + large morphs ⇒ memory, FD, and worker pressure.

**Partial library mitigation:** queue `maxsize=64` (drops when full).

**Solutions:**

| Layer | Action |
|-------|--------|
| Edge | Limit concurrent connections to `/ux-channel/push/*` per IP |
| App | Publish **small** regions (ticker strip), not full pages every tick |
| Interval | Cap feed frequency; coalesce updates |
| Multi-worker | Redis bus + connection limits per node |
| Monitor | Subscriber count, drop rate, publish size |

---

### 8. Multi-worker silent miss (availability / consistency)

**Issue:** Default `MemoryPushBus` is **process-local**. Publish on worker A, subscriber on worker B → **no events**.

**Impact:** Not classic confidentiality failure; causes stale UI and false confidence in “live” security monitoring.

**Solutions:**

- Single worker for small demos, **or**
- `REDIS_URL` / factory Redis push bus for multi-worker  
- Sticky sessions alone do **not** fix publish/subscribe cross-worker

---

### 9. Confusion with the action security model

**Issue:** Operators may assume caps, `auth=True`, and CSRF headers apply to live updates.

**Reality:**

| Path | Primary controls |
|------|------------------|
| `POST /action` | Cap, origin, header, rate limit, action auth |
| `GET /push/{topic}` | Optional shared token (+ whatever **you** add) |

**Solutions:** Document in runbooks; use SSE for **read-only UI patches** only; mutations always go through actions.

---

### 10. Topic name leakage & enumeration

**Issue:** Predictable topics (`orders`, `admin`, `user:{id}`) aid targeting.

**Solutions:** Opaque ids; separate public namespace; rate-limit 401/404 on push; don’t list topics on `/health` in production.

---

## Bottom line

| Statement | |
|-----------|--|
| **SSE is a transport for Results, not a second auth system.** | |
| **0.1 gives you an optional shared door (`push_token`) and a safe-enough public-board path.** | |
| **It does not give you per-user, per-tenant, or per-topic authorization.** | |
| **Confidential data on a guessable open topic is a vulnerability — by design gap, not a usage tip.** | |
| **Morph HTML is application-trusted content** — escape user data or you XSS every listener. | |
| **Mutations must not rely on SSE alone** — use signed actions. | |
| **Multi-worker live requires Redis (or equivalent) push**, or you are not actually live. | |

**One sentence:**  
Use SSE for **live, preferably public or ticket-gated, read-only region morphs**; use **actions + caps** for anything that changes authority or secrets; **escape HTML**; **token or ticket** anything that isn’t meant for the world.

---

## Solutions matrix (quick reference)

| Goal | Do this |
|------|---------|
| Public rate ticker | Open or light token; no PII; small morphs; rate-limit |
| Private shop board | `push_token` **or** subscribe ticket; opaque topic; HTTPS |
| Per-user stream | Ticket bound to `sub` + topic; never global token alone |
| Stop query-token leakage | Short TTL; Referrer-Policy; scrub logs; Bearer for non-browser |
| Stop XSS | `html.escape` in every region that touches user/feed data |
| Stop cross-worker miss | Redis push bus |
| Stop connection abuse | Edge limits on `/push/*` |
| Stop mistaken mutations | Only morph/toast on bus; orders/payments via `POST /action` |

### Config / code checklist (production)

```text
[ ] UX_CHANNEL_PUSH_TOKEN set (or explicit public-only design)
[ ] Private topics unguessable or ticket-checked
[ ] No long-lived master token in static HTML for private boards
[ ] Referrer-Policy set; HTTPS only
[ ] Region renderers escape user-controlled strings
[ ] Feed morphs minimal (ids, not full documents)
[ ] Redis push if >1 worker
[ ] Proxy timeouts allow long-lived SSE
[ ] Rate-limit GET /ux-channel/push/*
[ ] Mutations still require caps on /action
```

### Example: public board body

```python
# intentional open public feed
return HTMLResponse(
    f"<body {ch.body_attr_string(push_topic='sarrafa.public')}>..."
)
```

### Example: token-gated body (shared secret)

```python
# still not per-user — only "has shared secret"
body = ch.body_attr_string(
    push_topic="shop.lobby",
    push_token=os.environ["UX_CHANNEL_PUSH_TOKEN"],
)
```

### Example: publish safely

```python
from ux_channel.transport.push import get_push_bus

# After updating non-sensitive board state:
result = ch.refresh("board.ticker", "board.rates")  # renderers must escape
get_push_bus().publish("sarrafa.public", result)
```

---

## Related docs

| Doc | Role |
|-----|------|
| [SECURITY_AUDIT.md](../security/SECURITY_AUDIT.md) | Full control matrix (actions + SSE pointer) |
| [PRODUCTION.md](../production/PRODUCTION.md) | Deploy checklist |
| [FASTAPI.md](FASTAPI.md) | Routes |
| [RESULT.md](../core/RESULT.md) | Ops shape |
| [examples/sse_live_ticker/](../examples/sse_live_ticker/) | Auto-tick demo |

---


## Implemented production API (0.1)

```python
cfg = ChannelConfig.production(secret=os.environ["UX_CHANNEL_SECRET"])
# private board:
ticket = ch.sign_push("shop.lobby", sub=user_id)
html = f"<body {ch.body_attr_string(push_topic='shop.lobby', push_ticket=ticket)}>"

# public board:
html = f"<body {ch.body_attr_string(push_topic='public.rates')}>"

# shared service token:
cfg = ChannelConfig.production(secret=…, push_token=os.environ["UX_CHANNEL_PUSH_TOKEN"])
```

| Env / config | Meaning |
|--------------|---------|
| `UX_CHANNEL_PUSH_TOKEN` | Shared SSE secret |
| `UX_CHANNEL_PUSH_REQUIRE_AUTH` | Fail closed (default on in prod) |
| `UX_CHANNEL_PUSH_PUBLIC_PREFIXES` | Default `public.` |
| `UX_CHANNEL_PUSH_ALLOW_PUBLIC` | Default on |
| `UX_CHANNEL_PUSH_TICKET_MAX_AGE` | Default 300s |
| `ch.sign_push(topic, sub=…)` | Mint ticket |

Tests: `tests/webrtc/test_push_security.py`.

## Future library hardening (not in 0.1 core)

1. ~~Subscribe tickets~~ **done** (`sign_push`)  
2. ~~Production default-deny~~ **done** (`push_require_auth`)  
3. ~~Topic prefix policies~~ **done** (`public.*`)  
4. **Metrics**: subscribers, drops, bytes  
5. **Optional morph HTML sanitizer**  
6. Documented **Last-Event-ID** resume policy (sensitive replay!)  

---

*SSE security section for uxchannel 0.1 — issues, bottom line, and solutions.*


## Refresh reliability

- Server queues are bounded; on overflow the **oldest** event is dropped so clients prefer fresh morphs.
- EventSource **auto-reconnects**; apps should listen to `uid:pushError` for health UI (not only console).
- Keepalive comments (`: keepalive`) are ignored by browsers; they reset idle timeouts.
- Prefer `public.*` or tickets; failed auth is HTTP 401 (not a hung stream).
