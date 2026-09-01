<!-- pyramid -->
Read [../../../START_HERE.md](../../../START_HERE.md) first if you are new. This is Layer 2 (encyclopedia), not the intro.

# JS runtime load order & multi-script behaviour

## Scripts (stock)

| Script | Global | Role |
|--------|--------|------|
| `ux-channel.js` | `uxChannel` | Intent POST, morph, CSRF header, Signal→Intent (`data-channel-on`) |
| `ux-bridge.js` | `uxBridge` | Island registry (`register` / `apply` / `scan`) |
| `adapters/builtins.js` | (registers `builtin/*`) | first-party islands: confetti, particles, aurora, countup, spotlight |
| `adapters/widgets.js` | (registers vendor names) | leaflet, codemirror, quill, lottie-web, … |
| `ux-inspector.js` | `uidInspector` | Dev dock (optional) |
| `ux-webrtc.js` | `UxWebRTC` | RTC join helpers |
| `ux-sfu-livekit.js` | `UidMedia` | Optional SFU |

Recommended order (as in `demo_scripts` + adapters)::

```text
ux-channel.js → ux-bridge.js → ux-inspector? → ux-webrtc?
              → adapters/builtins.js → adapters/widgets.js
```

## Intended multi-load behaviour

| Situation | Intended | Notes |
|-----------|----------|-------|
| All scripts once, correct order | Mount islands, single click handler | Happy path |
| Second `ux-channel.js` | **No-op** (warn) | Avoids double Intent posts |
| Second `ux-bridge.js` | **No-op** (warn) | Preserves adapters + instances |
| Re-include `builtins` / `widgets` | Re-register packages + `scan` | Safe overwrite by name |
| Pack **before** `ux-bridge` | Warn + return; page stays up | Load bridge first, then the pack again |
| Multiple bridge hosts | Independent `instances[id]` | Different `data-channel-bridge-id` |
| Morph / remove host | `reaperBridges()` destroys orphans | Does **not** wipe unrelated DOM |
| Static siblings next to morph targets | Untouched | Only `data-channel-id` / bridge hosts change |

## Side effects that are **not** bugs

* Inspector wraps `postIntent` / bridge apply for the dock.
* WebRTC `bootAuto` only runs if `data-channel-webrtc-auto` is on `<body>`.
* widgets.js may pull CDN CSS/JS **on first mount** of that package (leaflet, quill, …) — network errors there do not break the channel.
* Confetti/particles append canvases **inside** their host only.
* Spotlight overlay is a pack-private `.ux-spotlight` child — not a `data-channel-*` attribute.

## Side effects that **were** bugs (fixed in 0.1)

1. **Double `<script ux-channel>`** bound click twice → 2× actions.
   Guard: `__UX_CHANNEL_RUNTIME_LOADED__`.
2. **Double `ux-bridge`** wiped the adapter registry.
   Guard: skip re-init if `uxBridge.register` exists.
3. **Defer order race**: channel `scan()` ran before packs registered → empty instances.
   Fix: channel rescan on microtask/0ms/50ms; adapters call `scan` after register.
4. **Raw `as_dict()` in HTML** broke `data-channel-args` → 401.
   Use `str(control)` / escaped attrs.



## Signal → Intent

Human signals become the same sealed Intent path as a click. There is **no**
client dual-bind store and **no** per-gesture attribute family.

### Interaction triad

| Attr | Role | Default |
|------|------|---------|
| `data-channel-action` | **WHAT** Intent (required on controls) | — |
| `data-channel-on` | **WHEN** (space-separated grammar) | `click`; inherits leaf signals from ancestors |
| `data-channel-target` | **WHERE** client morph hint | optional; inherits; server `morph` ops win |

Seal surface (not majors): `data-channel-args`, `data-channel-cap`,
`data-channel-idempotency`.

### `data-channel-on` grammar

```
entry     := signal | modifier
signal    := click | change | input | blur | longpress
           | swipe.left | swipe.right | swipe.up | swipe.down
           | swipe.horizontal | swipe.vertical   (synthesizers)
modifier  := delay:ms | threshold:px | throttle:ms | once
opt-out   := none | off
```

Modifiers bind to the **preceding** signal:

```html
<button data-channel-action="save">Save</button>
<!-- default on = click -->

<input name="q"
       data-channel-action="search.query"
       data-channel-on="input delay:200">

<div data-channel-on="swipe.horizontal threshold:48">
  <button data-channel-action="carousel.next"
          data-channel-on="click swipe.left">Next</button>
</div>
```

Defaults when a modifier is omitted: `input`/`change` → `delay:180`;
`longpress` → `delay:520`; swipe synthesizer → `threshold:48`.

### Value path

1. Typing lives in the DOM.
2. On signal, closest form → `Intent.form`. A named control (input/textarea/select)
   writes its live value into `Intent.form` too — never into `Intent.args`.
   Cap hashes `data-channel-args` only.
3. Server state is authority; **morph** writes canonical HTML.

Implements: `static/ux-channel.js`

### Live fields

`input` / `change` on the same control are latest-wins: a later signal
aborts the in-flight fetch (the `AbortController` already on
`postIntent`). The replaced Result does not morph and does not toast.
Click, swipe, and longpress still drop while in-flight (no double submit).
`delay:` is still the debounce before the first fire.



## Client persist vs morph restore-focus

These are two different facilities. Do not merge them. Closed-core doors:
[client-runtime.md](../../../docs/reference/client-runtime.md).

### Persist — optional flag on `signal.set`

Python mints. JS only applies. There is no second client store.

```python
st = state(ch, allow=["ui.theme"])          # allowlist for persist
st.client("ui.theme", "dark", persist=True) # mints signal.set + persist
```

| Step | What happens |
|------|----------------|
| Mint | `{op: "signal.set", path, value, persist: true}` after allowlist + `path_is_risky` + no `Quantity` |
| Apply | write `uxChannel.signals` path tree; if persist, write `localStorage["channel:sig:"+path]` |
| Live observe | `channel:signal` fires on apply only |
| Reload | `hydrateSignalsFromStorage` copies `channel:sig:*` back into the bag. Silent — no event, no DOM paint |

The bag survives reload. The HTML document does not come from the bag.
Paint after GET is server HTML (session/db) or product JS that *reads*
`uxChannel.signals`. Channel does not GET client values.

`st.session("n", 0)` is the counter. That is server draft + morph. It does
not use localStorage.

### Morph restore-focus — always on, not persist

On `morph` / outer `swap`, JS snapshots `document.activeElement` and
selection, then restores after the patch so a live field keeps the caret.
No body attribute. No `configure` knob. Not written to localStorage.

### Security (chrome only)

`localStorage` is origin-visible plaintext. XSS on the page can read and
write `channel:sig:*`. Persist is UI chrome (theme, locale, sidebar). It
is not a vault.

Python already refuses risky segments (`amount`, `token`, `secret`,
`password`, `balance`, …) and the `Quantity` type. An allowlist cannot
override that. Later modules that import channel must not treat
`uxChannel.signals` as a ledger.

Do not invent `data-channel-hydrate-signals` / `data-channel-restore-focus`
/ `uxChannel.store`.



## Live checks

```bash
PYTHONPATH=src python scripts/js_multi_live_chaos_server.py   # :8767
node scripts/js_multi_live_chaos.mjs http://127.0.0.1:8767
node scripts/js_live_chaos.mjs http://127.0.0.1:8766/         # single-script path
```

See also [CSRF_CHANNEL_HEADER.md](CSRF_CHANNEL_HEADER.md) · `BRIDGES.md` if present ·
[client-runtime.md](../../../docs/reference/client-runtime.md).
