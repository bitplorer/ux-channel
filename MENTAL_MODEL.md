**First-time users:** read [START_HERE.md](START_HERE.md) first.

# Mental model

The browser never invents business truth. It sends a signed **Intent**; the server runs an **action** and returns a **Result** of ordered **ops**.

```text
Browser                         Host (Channel)
───────                         ─────────────
control / form  ──Intent(+cap)──►  verify cap → action
DOM slots      ◄──Result(ops[])──  morph / toast / navigate / …
```

| Layer | Owns | Does not own |
|-------|------|--------------|
| **cek-runtime Host** (default `cek=require`) | mint / verify / once / sealed-args (one port Host; rust_wrap = reachability) | HTML, regions |
| **Channel** | `@on`, regions, classic IR, dispatch | markup trees, HTTP frameworks |
| **asgi** (L3 adapter) | FastAPI / Starlette mount | Intent / Cap law |
| **ux-dom** | Document / components | caps |

FastAPI is how a browser reaches the host. It is not the Channel. Headless: `Channel.boot(config=…)`. HTTP: `Channel.boot(app, host="fastapi")`. L4 planes (`ch.webrtc`, `ch.media`, `ch.bridge`) attach on first use — [LAYERS.md](python/src/ux_channel/LAYERS.md).

`dispatch` is sync. `async_dispatch` is the awaitable twin. Same law.

```text
boot → region / on → control → Intent → Result(ops)
```

You own HTML. Channel owns trust, regions, and ops.
