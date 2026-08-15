<!-- pyramid -->
Read [../../../START_HERE.md](../../../START_HERE.md) first if you are new. This is Layer 2 (encyclopedia), not the intro.

# The ux-channel Book (0.1)

> Library version **0.1.0**. Canonical API: region · on · done · control · draft.edit.

## 1. What it is

**ux-channel** is a control plane for server-driven UI:

1. Browser sends an **Intent** (action + args + capability).  
2. Server runs an **Action**.  
3. Server returns a **Result** of **ops** (morph, toast, navigate, …).  
4. Client applies ops — no client VDOM framework required.

## 2. Mental model

| Piece | Owns |
|-------|------|
| ux-dom / Jinja / HTML | Markup & widgets |
| Channel | Protocol, caps, regions, dispatch |
| Region | One morphable `data-channel-id` slot |
| Cap | Authorization for one action+args snapshot |

Golden rule: **caps carry ids; loaders re-read truth; morph only what changed.**

## 3. First app

See [../GOLDEN_PATH.md](../start/GOLDEN_PATH.md) and [../FASTAPI.md](../asgi/FASTAPI.md).

```python
ch = Channel.boot(app, config=ChannelConfig.development(secret="…", allow_memory_stores=True))

@ch.region
def badge(ctx): ...

@ch.on(refresh=[badge])
def add(product_id: str = "sku"):
    ch.draft.change("n", lambda n: (n or 0) + 1, default=0)
    return ch.done(notice="Added")
```

## 4. Security (summary)

- HMAC capabilities (`require_cap`)  
- CSRF-class header in production  
- Origin checks  
- Unsafe href schemes stripped  
- Escape user HTML in morphs  

Full matrix: [../SECURITY_AUDIT.md](../security/SECURITY_AUDIT.md).

## 5. Concurrency

Use `ch.draft.edit` / `change` / `merge`. Do not compose bare `get`+`set` under threads.

## 6. Async

`async def` actions and hooks are supported. Prefer `async with ch.draft.edit(...)` inside async actions.

## 7. Multi-instance regions

Class `Region` action wire names are `{uid}.{method}` so many instances can coexist.

## 8. What 0.1 is not

- Not a React replacement with client components  
- Not an HTML component library (ux-dom stays free)  
- Not multi-worker-safe with memory stores alone  

## 9. Doc map

| Doc | Use |
|-----|-----|
| [HOW_TO.md](../start/HOW_TO.md) | Practical guide |
| [API.md](../start/API.md) | API surface |
| [EXAMPLES.md](../dx/EXAMPLES.md) | Patterns |
| [PRODUCTION.md](../production/PRODUCTION.md) | Deploy |

---

*End of The ux-channel Book (0.1).*

## 10. Live SSE (0.1)

Without user clicks, a feeder publishes Results:

```python
get_push_bus().publish("live.board", ch.refresh(ticker))
```

The browser auto-subscribes when:

```html
<body data-channel-push-topic="live.board" …>
```

`ux-channel.js` opens EventSource and calls `applyResult`. Demo: `examples/sse_live_ticker/`.

## Live bind vs push vs Redis (0.1)

| API | What it is |
|-----|------------|
| `ch.live.bind(topic, *regions)` | In-process **topic → region uids** map only |
| `ch.live.publish(topic)` | Refresh bound regions → **push bus** |
| Client `push_topic` / WS subscribe | Browser asks for Results on that topic |
| Redis (optional) | Push bus / nonce / rate **backend** across workers |

`bind` is **not** Redis `SUBSCRIBE` and does not open a client connection.

