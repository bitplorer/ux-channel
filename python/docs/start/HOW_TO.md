# How to use ux-channel 0.1.0

### Brand lines

| Layer | Name |
|-------|------|
| **PyPI / pip** | `ux-channel` |
| **Import** | `ux_channel` |
| **CLI** | **`uxchannel`** |


## 1. Install

```bash
pip install "ux-channel[fastapi]"
# optional: redis, pydantic, dev
pip install "ux-channel[fastapi,redis,dev]"
```

Python **3.10+**.

```bash
uxchannel info
uxchannel doctor
uxchannel profile
uxchannel dashboard

Error patterns: [ERROR_HANDLING.md](./ERROR_HANDLING.md)
```

## 2. Boot on FastAPI

```python
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from ux_channel import Channel, ChannelConfig, Region

app = FastAPI()
ch = Channel.boot(
    app,
    config=ChannelConfig.development(
        secret="dev-secret-key-32chars-minimum!!!!",
        allow_memory_stores=True,
    ),
)
```

Production:

```python
import os
ch = Channel.boot(
    app,
    config=ChannelConfig.production(secret=os.environ["UX_CHANNEL_SECRET"]),
)
```

Details: [FASTAPI.md](../asgi/FASTAPI.md).

## 3. Regions (SSR slots)

```python
@ch.region
def cart_badge(ctx):
    n = ch.draft.get("n", 0)
    return f'<span data-channel-id="cart_badge">Cart ({n})</span>'

# paint
ch.html(cart_badge)           # wrapped fragment
ch.html("cart_badge")         # by uid string
```

### Class regions

```python
class CartBadge(Region):
    def render(self, ctx):
        n = self.ch.draft.get("n", 0)
        return f'<span data-channel-id="{self.uid}">Cart ({n})</span>'

    @Region.action  # wire name defaults to "{uid}.{method}"
    def add(self, product_id: str = "sku"):
        with self.ch.draft.edit("n", default=0) as slot:
            slot.value += 1

badge = ch.use(CartBadge)  # mounts region + actions
```

## 4. Actions

```python
@ch.on(refresh=[cart_badge])
def add(product_id: str = "sku"):
    ch.draft.change("n", lambda n: (n or 0) + 1, default=0)
    return ch.done(notice=f"Added {product_id}")

@ch.on(name="Orders.place", auth=True, once=True)
async def place(order_id: str):
    # await db...
    return ch.done(notice="Placed", refresh=["orders.list"])
```

| Return | Meaning |
|--------|---------|
| `ch.done(...)` | Success + optional notice + refresh |
| `ch.fail.valid(...)` | Field errors + optional morph |
| `ch.fail.auth()` | Unauthorized |
| `None` (with decorator toast/refresh) | Same as `ch.done` defaults |
| `Result` / op list | Low-level encode path |

Async `async def` actions are supported and **do run** (registration preserves async).

## 5. Controls (wire the DOM)

```python
# signed trust args (server-sealed)
attrs = ch.control(add, trust_product_id="sku").as_dict()
# → data-channel-action, data-channel-args, data-channel-cap

# ux-dom
button("Add", type="button", **ch.control(add, trust_product_id="sku").as_ux_dom())
```

Client JS posts Intent to `/ux-channel/action` with the cap. Tampered sealed args → `unauthorized`.

## 6. Draft state (atomic RMW)

`get` + `set` are each atomic; **the pair is not**.

```python
# preferred
with ch.draft.edit("n", default=0) as slot:
    slot.value += 1

async with ch.draft.edit("n", default=0) as slot:  # inside async actions
    slot.value += 1

ch.draft.change("n", lambda n: (n or 0) + 1, default=0)
ch.draft.merge("form", email=email)
```

## 7. Page shell

```python
@app.get("/", response_class=HTMLResponse)
def index():
    a = ch.control(add, trust_product_id="sku").as_dict()
    attr = " ".join(f'{k}="{v}"' for k, v in a.items())
    return f"""<!doctype html>
<html>
<head>{ch.scripts()}</head>
<body {ch.body_attr_string()}>
  {ch.html(cart_badge)}
  <button type="button" {attr}>Add</button>
</body>
</html>"""
```

## 8. Intent / Result (wire)

**Intent (client → server)**

```json
{
  "v": "1",
  "action": "add",
  "args": { "product_id": "sku" },
  "cap": "<hmac token>",
  "request_id": "req_…"
}
```

**Result (server → client)**

```json
{
  "v": "1",
  "ok": true,
  "ops": [
    { "op": "morph", "target": "[data-channel-id=\"cart_badge\"]", "html": "…" },
    { "op": "toast", "message": "Added sku", "level": "info" }
  ],
  "meta": { "action": "add", "duration_ms": 1.2, "runtime": "0.1.0" }
}
```

Dangerous navigate schemes (`javascript:`, `data:`, `//…`) are stripped server-side.

## 9. Security checklist

- Long secret (`UX_CHANNEL_SECRET`)
- Production: `ChannelConfig.production`
- Escape user content in region HTML
- Multi-worker: Redis for nonce / rate / state
- See [SECURITY_AUDIT.md](../security/SECURITY_AUDIT.md)

## 10. Hooks

```python
@ch.before
def rate(intent, args):
    ...
    return None  # or Result.fail(...)

@ch.after
def audit(intent, result):
    return result  # must return Result (None is ignored)
```

Async hooks work on sync dispatch when no event loop is running.

## 11. Testing

```python
from fastapi.testclient import TestClient
from ux_channel import Intent

client = TestClient(app)
cap = ch.mint("add", {"product_id": "sku"})
r = client.post(
    "/ux-channel/action",
    json={"action": "add", "args": {"product_id": "sku"}, "cap": cap},
    headers={"X-UID-Channel": "1"},
)
assert r.json()["ok"]
```

## 12. Diagnostics

```python
ch.diagnose()
# path, action_endpoint, actions, regions, environment, ...
```

## Next

[EXAMPLES.md](../dx/EXAMPLES.md) · [REGIONS.md](../regions/REGIONS.md) · [API.md](API.md) · [PRODUCTION.md](../production/PRODUCTION.md)

## 13. Live SSE (no clicks)

Server publishes Results; browser EventSource applies them automatically.

```python
from ux_channel.transport.push import get_push_bus

# body: ch.body_attr_string(push_topic="live.board")
result = ch.refresh(ticker_region)
get_push_bus().publish("live.board", result)
```

Full guide: [SSE.md](../asgi/SSE.md) · demo: `examples/sse_live_ticker/`.

## I/O channel on mesh (not a driver)

Full constitution: [IO_CHANNEL.md](../workplace/IO_CHANNEL.md).

```python
from ux_channel.foundations.io_channel import IoGate, claim_from_ticket_claims, run_checked
from ux_channel.io_adapters import ScannerAdapter, LightsAdapter, LabDutAdapter
```

1. Build `IoRoomClaim` from a ticket (`claim_from_ticket_claims`).
2. `run_checked(gate, adapter, method, args, claim=…, quantity=…)` for commands.
3. Adapter events → `gate.check_event` → same `@ch.on` / `agents(ch).dispatch` as buttons.
4. Never put device drivers in core — implement `IoAdapter` in app code.

Demo: `examples/io_mesh_workplace/`.

## Workplace (policy-shaped room)

```python
from ux_channel.workplace import workplace

wp = workplace(ch, ticket={"room": "pos", "peer_id": "c1", "scopes": ["pos", "add"]})
wp.allow(scanner)
wp.dispatch("add_line", {"sku": "X"})
wp.run_io("pos.scanner", "read")
```

Full guide: [WORKPLACE.md](../workplace/WORKPLACE.md).

## Three surfaces (button · agent · adapter)

See [THREE_SURFACES.md](../workplace/THREE_SURFACES.md).

```python
from ux_channel.workplace import issue_mesh_membership, workplace_from_membership

mem = issue_mesh_membership(ch, "pos", sub="c1", scopes=["pos", "add", "scan"])
wp = workplace_from_membership(ch, mem).allow(scanner)
wp.control(add_line, trust_sku="X")
wp.dispatch("add_line", {"sku": "X"})
```

## Profile (first-class DX)

```bash
uxchannel profile
uxchannel profile --out ./reports/p95 --json-report
```

Writes `reports/p95/report.html`, `latency.json`, and `profile.speedscope.json`
(open in speedscope.app). App source is never modified.
