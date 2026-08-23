# First working app (copy-paste)

> **Diátaxis:** how-to · **Canonical:** `docs/guides/first-app.md` · **Layer:** ux-channel  
> Map: [INDEX.md](../INDEX.md).

Extracted from root `START_HERE.md` (Phase 2 mixed-mode split). The 5-minute path stays at [../../START_HERE.md](../../START_HERE.md).

## 7. First working app (copy-paste)

Requires: Python 3.10+, `fastapi`, `uvicorn` (or any supported host).

```python
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from ux_channel import Channel, ChannelConfig

app = FastAPI()
ch = Channel.boot(
    app,
    config=ChannelConfig.development(
        secret="dev-secret-key-32chars-minimum!!!!",  # ≥32 chars in real apps
        allow_memory_stores=True,
    ),
)

@ch.region
def badge(ctx):
    n = ch.draft.get("n", 0) or 0
    return f'<span data-channel-id="badge">Cart ({n})</span>'

@ch.on(refresh=[badge], idempotent=False)
def add(product_id: str = "sku"):
    ch.draft.change("n", lambda n: (n or 0) + 1, default=0)

@app.get("/", response_class=HTMLResponse)
def index():
    attrs = ch.control(add, trust_product_id="sku").as_dict()
    attr_s = " ".join(f'{k}="{v}"' for k, v in attrs.items())
    return f"""<!doctype html>
<html>
<head>{ch.scripts()}</head>
<body {ch.body_attr_string()}>
  {ch.html(badge)}
  <button type="button" {attr_s}>Add</button>
</body>
</html>"""
```

**What you should observe**

1. Page loads with Cart (0).  
2. Click **Add** → Intent with cap → handler → region refresh → morph → Cart (1).  
3. Tampering with signed args without a new cap fails verification.

**Day-1 explicitly *not* required**

- Redis, WebRTC, MCP, agent_runtime  
- Hand-rolled `ActionRegistry` + `mount_channel` (boot does this)  
- CXB (JSON is enough)

More: [python/docs/start/GOLDEN_PATH.md](../../python/docs/start/GOLDEN_PATH.md) · [python/docs/start/HOW_TO.md](../../python/docs/start/HOW_TO.md)

---

## 13. Checklist: “I understand enough to build”

- [ ] I can draw Intent → verify → action → Result → ops without notes  
- [ ] I know why **args_hash** exists and what happens if args change after mint  
- [ ] I know region vs full navigate  
- [ ] I know session vs client vs db state  
- [ ] I can boot a Channel and wire one button with `control`  
- [ ] I know what **not** to import from root  
- [ ] I know optional planes (agents, MCP, WebRTC) are doors, not the core loop  
- [ ] I know conformance vectors beat folklore  

When all boxes are checked, you are no longer a first-time user — build the product, and open [LONGEVITY.md](../../LONGEVITY.md) before adding a new package.
