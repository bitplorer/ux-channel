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
| **cek-host** (optional `cek=require`) | mint / verify / once / sealed-args | HTML, regions |
| **Channel** | `@on`, regions, classic IR, FastAPI | markup trees |
| **ux-dom** | Document / components | caps |

`dispatch` is sync. `async_dispatch` is the awaitable twin. Same law.

```text
boot → region / on → control → Intent → Result(ops)
```

You own HTML. Channel owns trust, regions, and ops.