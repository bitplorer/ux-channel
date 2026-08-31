# Browser runtime — closed core, four doors

> **Diátaxis:** reference · **Layer:** ux-channel client
> Policy: [../../LONGEVITY.md](../../LONGEVITY.md). Host doors: [../../python/docs/start/EXTENSIONS.md](../../python/docs/start/EXTENSIONS.md).

The browser never invents business truth. It sends an **Intent** and applies
a **Result** of ordered **ops**.

```text
When (data-channel-on) → Intent → Result.ops[] → apply
apply = beforeApply → each op (beforeOp / applyOp / afterOp) → afterApply
```

## Doors (use these; do not edit the core switch)

| Need | Door |
|------|------|
| New effect (`transition.play`, product op) | `uxChannel.registerOp(name, fn)` |
| Cross-cutting | `uxChannel.on("channel:beforeApply" \| "channel:beforeOp" \| "channel:afterOp" \| "channel:afterApply", fn)` |
| Intended side effects | `uxChannel.configure({ autoToast, restoreFocus, hydrateStore, … })` |
| Islands / fx | `uxBridge.register(pkg, impl)` |

`registerOp` returns `false` and refuses names in the frozen core set
(`morph`, `swap`, `navigate`, `signal.set`, `bridge.*`, `timer.*`, …).
Unknown ops emit `channel:unknownOp` and no-op. No `eval`.

## Names

| Name | Role |
|------|------|
| When | `data-channel-on` — DOM event → Intent |
| Store | `uxChannel.store` — client bag (`signal.set`). `signals` is an alias |
| Morph | core op — server HTML patch |
| Play | registered op — motion runtime, after morph in the same `ops[]` |

## Body attrs (same defaults as today)

`data-channel-auto-toast="0"` · `data-channel-restore-focus="0"` ·
`data-channel-hydrate-store="0"` · existing error-log / field-errors attrs.

Defaults keep current behaviour: toast on error, restore focus/scroll on morph,
hydrate store from `localStorage`.
