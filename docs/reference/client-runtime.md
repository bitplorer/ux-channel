# Browser runtime — closed core, four doors

> **Diátaxis:** reference · **Layer:** ux-channel client
> Policy: [../../LONGEVITY.md](../../LONGEVITY.md). Host doors: [../../python/docs/start/EXTENSIONS.md](../../python/docs/start/EXTENSIONS.md).

The browser never invents business truth. **Python (or a driver) mints the op.**
This file only applies the payload the server already sent.

```text
Python action / driver
  → Result.ops[]          name, target, html, play id, …
       ↓
When (data-channel-on) → Intent → Result.ops[] → apply
apply = beforeApply → each op (beforeOp / applyOp / afterOp) → afterApply
```

`registerOp` is an **apply adapter**, not a second place to define product
operations. Do not put `if (count > 3)` or routing rules in the handler.

## Doors (use these; do not edit the core switch)

| Need | Door |
|------|------|
| Apply a non-core op the server already minted | `uxChannel.registerOp(name, fn)` |
| Cross-cutting observer | `uxChannel.on("channel:beforeApply" \| "channel:beforeOp" \| "channel:afterOp" \| "channel:afterApply", fn)` |
| Intended side effects | `uxChannel.configure({ autoToast, restoreFocus, hydrateStore, … })` |
| Islands / fx | `uxBridge.register(pkg, impl)` |

`registerOp` returns `false` for **exact** core case names (`morph`, `swap`,
`navigate`, `signal.set`, `bridge.mount`, `timer.set`, …). It is not a prefix
freeze — `registerOp("bridge.chart")` is allowed. Unknown ops emit
`channel:unknownOp` and no-op. No `eval`. Last register for a name wins.

## Names

| Name | Role |
|------|------|
| When | `data-channel-on` — DOM event → Intent |
| Store | `uxChannel.store` — client bag (`signal.set`). `signals` is an alias |
| Morph | core op — server HTML patch |
| Play | registered apply adapter — motion runtime plays the plan Python minted |

## Body attrs (same defaults as today)

`data-channel-auto-toast="0"` · `data-channel-restore-focus="0"` ·
`data-channel-hydrate-store="0"` · existing error-log / field-errors attrs.

Defaults keep current behaviour: toast on error, restore focus **and scroll**
on morph, hydrate store from `localStorage` at boot.

`hydrateStore` only controls that boot read. A server `signal.set` with
`persist: true` still writes. `restoreFocus: false` skips both focus and
scroll snapshot on morph.
