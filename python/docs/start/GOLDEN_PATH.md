<!-- pyramid -->
Read [../../../START_HERE.md](../../../START_HERE.md) first if you are new. This is Layer 2 (encyclopedia), not the intro.

**First-time users:** [START_HERE.md](../../../START_HERE.md) (mental model, caps, mistakes, checklist).

> **Media-first (application):** prefer ``ch.media.plugin(room, sub=…)`` (``mode='mesh'|'sfu'|'auto'``). ``ch.webrtc`` remains the mesh power plane.

# Golden path — uxchannel 0.1

**Learn only this.** Everything else is power tools or layers.

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
    n = ch.draft.get("n", 0) or 0
    return f'<span data-channel-id="badge">Cart ({n})</span>'

@ch.on(refresh=[badge], idempotent=False)
def add(product_id: str = "sku"):
    ch.draft.change("n", lambda n: (n or 0) + 1, default=0)

@app.get("/", response_class=HTMLResponse)
def index():
    # Production: ux-dom component + **ch.control(...).as_dict()
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

## Optional P2P (still application shaped)

```python
ticket = ch.webrtc.sign_ticket("lobby", sub=user_id)
# in page:
#   {ch.scripts()}  # includes ux-webrtc.js when enabled
#   <body {ch.body_attr_string(webrtc="lobby")}>
# client: UxWebRTC.join({ room: "lobby", rtcPath: ch.webrtc.path, ticket })
```

## What not to do on day 1

* Import `ActionRegistry` / `mount_channel` by hand  
* Learn SFU/WHIP/scaffold APIs  
* Build UI with `ch.button` in a real product (use ux-dom)  
* Put WebRTC helpers on `from ux_channel import …`  

```python
print(Channel.describe())
```

Next: [API_SURFACE.md](API_SURFACE.md) · [WEBRTC.md](../webrtc/WEBRTC.md) · [SCAFFOLD.md](../dx/SCAFFOLD.md)
