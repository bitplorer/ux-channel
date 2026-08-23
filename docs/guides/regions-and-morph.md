# Regions, morph, and the HTML door

> **Diátaxis:** how-to · **Canonical:** `docs/guides/regions-and-morph.md` · **Layer:** ux-channel  
> Map: [INDEX.md](../INDEX.md).

Extracted from root `START_HERE.md` (Phase 2 mixed-mode split). The 5-minute path stays at [../../START_HERE.md](../../START_HERE.md).

## 5. Regions, morph, and HTML

### Region

A **region** is a server function that returns HTML (or a value the renderer turns into HTML) for a **stable uid**. After an action, the host can re-run regions and emit **morph** ops so the client patches only those slots.

```text
@ch.region
def badge(ctx):
    ...
    return '<span data-channel-id="…">…</span>'
```

### Why not return a whole new page every time?

You can `navigate` when you mean full navigation. For in-place UI, **ops** keep the protocol stable and cache-friendly across peers.

### Control attrs

`ch.control(handler, trust_…)` produces attributes the client/runtime uses to build an Intent (action name, cap, sealed args).  
Day-1 apps often stringify those attrs onto a `<button>`. Production apps often feed them into **ux-dom** / your component system — the **protocol** stays the same.

### Scripts / body attrs

`ch.scripts()` / body helpers inject the client runtime needed to POST Intents and apply ops. Without them, buttons have caps but nothing speaks the wire.

---

This page is the **protocol** door (region uid, morph ops, control attrs). This repo does **not** own HTML trees or CSS — markup lives in **ux-dom**.
