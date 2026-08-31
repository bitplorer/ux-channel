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
| Existing intended side effects | `uxChannel.configure({ autoToast, … })` |
| Islands / fx | `uxBridge.register(pkg, impl)` |

`configure` keeps the error-plane knobs that already existed on main
(`autoToast`, `toastRefreshErrors`, `fieldErrors`, `logSize`, `dedupeMs`,
proofs). It does not grow a hydrate or restore-focus knob.

`registerOp` returns `false` for **exact** core case names (`morph`, `swap`,
`navigate`, `signal.set`, `bridge.mount`, `timer.set`, …). It is not a prefix
freeze — `registerOp("bridge.chart")` is allowed. Unknown ops emit
`channel:unknownOp` and no-op. No `eval`. Last register for a name wins.

## Names

| Name | Role |
|------|------|
| When | `data-channel-on` — DOM event → Intent |
| Signals | `uxChannel.signals` — client bag written only by `signal.set` |
| Morph | core op — server HTML patch |
| Play | registered apply adapter — motion runtime plays the plan Python minted |

Do not call the bag `store`. That word already means host / session stores
(`MemoryStateStore`, `Quantity.from_store`). Persist is an optional flag on
`signal.set`, not a second public object.

The bag is a generic path tree. Any allow-listed path the server mints can
live there — theme, chrome, wizard step, whatever the product needs. The
runtime does not special-case a use.

## Persist and boot hydrate (Python mints, JS applies)

```python
st = state(ch, allow=["ui.theme"])
st.client("ui.theme", "dark", persist=True)
```

JS writes `uxChannel.signals` and, when the op carries `persist: true`, the
matching `localStorage` key (`channel:sig:` + path). Next boot re-reads those
keys silently via `hydrateSignalsFromStorage`. No body attribute and no
`configure` knob gates that read.

Focus and scroll restore on morph stay as they were on main — always on,
not a second public switch.

## Body attrs (same as main)

`data-channel-auto-toast="0"` · `data-channel-toast-refresh-errors` ·
`data-channel-field-errors="0"` · `data-channel-error-log="32"` · existing
endpoint / concurrency / timeout / push / ws attrs.

Cap hashes `data-channel-args`. The cap does not embed argument values, so
the sealed Intent payload stays on `data-channel-args`.
