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

The bag is not paint. After reload the document is a fresh HTML GET.
Session/db re-enter through the server. Product JS that needs a chrome
class from the bag reads `uxChannel.signals` after this file has booted.
`channel:signal` fires on live `signal.set` apply, not on silent hydrate.

Focus and scroll restore on morph stay as they were on main — always on,
not a second public switch, not written to `localStorage`.

`data-ux-keep-value` is a separate opt-in. On morph (and outer swap, which
calls the same path), the client copies the live `.value` onto a `textarea`,
or onto an `input` of type `password`, `text`, `email`, `search`, `tel`, or
`url`. Those six types are one class, so a password field can become `text`
on Show and keep what was typed. Textarea matches only textarea. Any other
control (`hidden`, `checkbox`, `radio`, `file`, `select`) ignores the mark
and logs one console warning. The copy is the DOM property `el.value`, one
element at a time inside try/catch. A throw while reading or writing one
field skips that field and logs one warning that names the error; the other
fields continue. The name is `error.message` when that is a non-empty
string. An empty message uses the constructor name, or `Error` when that
name is empty. Otherwise the name is `String(error)`, or `unknown error`
when that throws. The thrown value is
the second `console.warn` argument. Two fields that throw the same message
each log a warning; the same field logs one, including when a nested morph
runs during this one. If Idiomorph throws, the error is
reported the same way as any other failed morph, and kept values for the
other fields are still restored. The partial morph is left in place. A throw
while restoring kept values, including while listing the marked fields, only
logs that warning. It does not replace a morph error, and it does not create
an op error when the morph succeeded. The same holds when the page has no
Idiomorph and the client uses `replaceWith`. If the saved element throws
while it is being matched, or a node's key
cannot be decided, that field is not restored and the value is not written
into a different field. A different field's throw does not clear the
others. The throw logs the same warning.
It does not set `.checked`, the value
attribute, parse the text, or insert a node, and it does not send the value
to the server. A field matches only when both nodes still have the mark, the same `name`,
and the same class. The key is `JSON.stringify` of the closest ancestor
`data-channel-id` (or `""`), the form identity (`id:`, `name:`, `unnamed`,
or `none`), the field `name`, and the kind class. Every form is scoped by
that component, so a form moving from component a to component b does not
keep the value. An unnamed form with no component root restores nothing and
logs one console warning, the same as a field with no form and no component
root. One warning is logged per ignored field per morph. A marked field
with no `name` restores nothing and logs one warning, including inside a
form or a component. A field that has a name, inside a named form or
inside a component, does not log that warning. `id` is
not the key. Shared keys restore nothing. The server should paint
`value=""` for secrets.

### What persist is not

| Want | Use |
|------|-----|
| Counter / wizard draft | `st.session(...)` then morph |
| Money, stock, dose, roles | your DB + `Quantity.from_store` |
| Secret / token / cap | never the client bag |
| Caret after morph | already on — `restoreFocus` inside applyMorph |
| Live value across morph | `data-ux-keep-value` on a textarea or a text-like input (`password`, `text`, `email`, `search`, `tel`, `url`) |

### Client-storage threat model

`localStorage` is origin-scoped plaintext. Any script on the page (XSS)
can read and write `channel:sig:*`. Persist is therefore **chrome only**.

Write gate is Python, not the browser:

- `state(ch, allow=[...])` — persist requires exact path membership
- `path_is_risky` — `amount` / `token` / `secret` / `password` / `balance` / …
  cannot be persisted; allowlist cannot override
- `Quantity` values rejected
- default `strict=True` also blocks risky paths without persist

Hydrate trusts keys already under `channel:sig:`. Channel does not send
the bag back as authority. Later modules must not treat
`uxChannel.signals` as a ledger. Quota / private-mode failures are
swallowed on write so a full disk cannot kill apply.

## Body attrs (same as main)

`data-channel-auto-toast="0"` · `data-channel-toast-refresh-errors` ·
`data-channel-field-errors="0"` · `data-channel-error-log="32"` · existing
endpoint / concurrency / timeout / push / ws attrs.

Cap hashes `data-channel-args`. The cap does not embed argument values, so
the sealed Intent payload stays on `data-channel-args`.
