<!-- pyramid -->
Read [../../../START_HERE.md](../../../START_HERE.md) first if you are new. This is Layer 2 (encyclopedia), not the intro.

# Examples — uxchannel 0.1

## FastAPI + function regions

```python
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from ux_channel import Channel, ChannelConfig

app = FastAPI()
ch = Channel.boot(
    app,
    config=ChannelConfig.development(
        secret="dev-secret-key-32chars-minimum!!!!",
        allow_memory_stores=True,
    ),
)

@ch.region
def badge(ctx):
    n = ch.draft.get("n", 0)
    return f'<span data-channel-id="badge">Cart ({n})</span>'

@ch.on(refresh=[badge])
def add(product_id: str = "sku"):
    ch.draft.change("n", lambda n: (n or 0) + 1, default=0)
    return ch.done(notice=f"Added {product_id}")

@app.get("/", response_class=HTMLResponse)
def index():
    d = ch.control(add, trust_product_id="sku").as_dict()
    attrs = " ".join(f'{k}="{v}"' for k, v in d.items())
    return f"""<!doctype html>
<html><head>{ch.scripts()}</head>
<body {ch.body_attr_string()}>
  {ch.html(badge)}
  <button type="button" {attrs}>Add</button>
</body></html>"""
```

## Class Region + ux-dom

```python
from ux_dom import Document
from ux_dom.dom import button, div, raw
from ux_channel import Region

class CartBadge(Region):
    def render(self, ctx):
        n = self.ch.draft.get("n", 0)
        return f'<span data-channel-id="{self.uid}">Cart ({n})</span>'

    @Region.action
    def add(self, product_id: str = "sku"):
        with self.ch.draft.edit("n", default=0) as s:
            s.value += 1

badge = ch.use(CartBadge)
document = Document(head=[raw(str(ch.scripts()))])

@app.get("/")
def index():
    return document(
        div(
            raw(badge()),
            button(
                "Add",
                type="button",
                **ch.control(badge.add, trust_product_id="sku").as_ux_dom(),
            ),
        )
    )
```

## Auth + roles

```python
@ch.on(name="Admin.wipe", auth=True, roles=["admin"], once=True)
async def wipe():
    return ch.done(notice="wiped")
```

## Validation fail

```python
@ch.on(name="Form.save", refresh=["form.panel"])
def save(email: str = ""):
    if "@" not in email:
        return ch.fail.valid({"email": ["invalid"]}, message="Check email")
    return ch.done(notice="Saved")
```

## Draft concurrency

```python
# good
ch.draft.change("n", lambda n: (n or 0) + 1, default=0)
with ch.draft.edit("form", default={}) as s:
    s.value["email"] = email

# bad under threads
n = ch.draft.get("n", 0)
ch.draft.set("n", n + 1)
```

## Rename map (older drafts → 0.1)

| Old | 0.1 |
|-----|-----|
| `@ch.view` / island | `@ch.region` |
| `ch.islands` | `ch.regions` |
| `ch.sync` / revalidate | `ch.refresh` / `ch.done(refresh=)` |
| `ch.bind` | `ch.control` |
| `args=` sealed | `trust_*` / trust map |
| `get`+`set` RMW | `edit` / `change` / `merge` |
| `Class.method` action | `{uid}.{method}` |

## Live SSE ticker (no clicks)

`ch.live.bind(topic, *regions)` only records which regions to refresh; it does **not** subscribe Redis or the browser. Client still needs `push_topic` / WS. Redis is optional PushBus backend for multi-worker.


```python
from ux_channel.transport.push import get_push_bus

@ch.region
def ticker(ctx):
    n = ch.draft.get("n", 0)
    return f'<div data-channel-id="ticker">ticks {n}</div>'

# feeder:
# ch.draft.change("n", lambda n: (n or 0) + 1, default=0)
# get_push_bus().publish("live.board", ch.refresh(ticker))

@app.get("/")
def index():
    return f"""<!doctype html>
<html><head>{ch.scripts()}</head>
<body {ch.body_attr_string(push_topic="live.board")}>
  {ch.html(ticker)}
</body></html>"""
```

Runnable: `examples/sse_live_ticker/` · docs: [SSE.md](../asgi/SSE.md).

## Live demos (0.1)

| Demo | Transport |
|------|-----------|
| `examples/sse_live_ticker/` | SSE EventSource + `public.*` topics |
| `examples/ws_live_board/` | WebSocket duplex + ticket for private topics |
| `examples/sarrafa_market/` | Action-driven market board (ux-dom) |
| `examples/ux_dom_chartjs/` | Bridge → Chart.js |
| `examples/ux_dom_threejs/` | Bridge → three.js |
