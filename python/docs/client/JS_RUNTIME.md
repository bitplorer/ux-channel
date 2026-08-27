<!-- pyramid -->
Read [../../../START_HERE.md](../../../START_HERE.md) first if you are new. This is Layer 2 (encyclopedia), not the intro.

# JS runtime load order & multi-script behaviour

## Scripts (stock)

| Script | Global | Role |
|--------|--------|------|
| `ux-channel.js` | `uxChannel` | Intent POST, morph, CSRF header, Signal→Intent (`data-channel-on`) |
| `ux-bridge.js` | `uxBridge` | Island registry (`register` / `apply` / `scan`) |
| `adapters/ux-fx.js` | (registers packages) | confetti, particles, countup, … |
| `adapters/ux-ui.js` | (registers packages) | leaflet, codemirror, quill, … |
| `ux-inspector.js` | `uidInspector` | Dev dock (optional) |
| `ux-webrtc.js` | `UxWebRTC` | RTC join helpers |
| `ux-sfu-livekit.js` | `UidMedia` | Optional SFU |

Recommended order (as in `demo_scripts` + adapters)::

```text
ux-channel.js → ux-bridge.js → ux-inspector? → ux-webrtc?
              → adapters/ux-fx.js → adapters/ux-ui.js
```

## Intended multi-load behaviour

| Situation | Intended | Notes |
|-----------|----------|-------|
| All scripts once, correct order | Mount islands, single click handler | Happy path |
| Second `ux-channel.js` | **No-op** (warn) | Avoids double Intent posts |
| Second `ux-bridge.js` | **No-op** (warn) | Preserves adapters + instances |
| Re-include `ux-fx` / `ux-ui` | Re-register packages + `scan` | Safe overwrite by name |
| `ux-fx` **before** `ux-bridge` | Warn + return; page stays up | Load bridge first, then fx again |
| Multiple bridge hosts | Independent `instances[id]` | Different `data-channel-bridge-id` |
| Morph / remove host | `reaperBridges()` destroys orphans | Does **not** wipe unrelated DOM |
| Static siblings next to morph targets | Untouched | Only `data-channel-id` / bridge hosts change |

## Side effects that are **not** bugs

* Inspector wraps `postIntent` / bridge apply for the dock.
* WebRTC `bootAuto` only runs if `data-channel-webrtc-auto` is on `<body>`.
* ux-ui may pull CDN CSS/JS **on first mount** of that package (leaflet, quill, …) — network errors there do not break the channel.
* Confetti/particles append canvases **inside** their host only.

## Side effects that **were** bugs (fixed in 0.1)

1. **Double `<script ux-channel>`** bound click twice → 2× actions.  
   Guard: `__UX_CHANNEL_RUNTIME_LOADED__`.
2. **Double `ux-bridge`** wiped the adapter registry.  
   Guard: skip re-init if `uxBridge.register` exists.
3. **Defer order race**: channel `scan()` ran before ux-fx registered → empty instances.  
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


## Live checks

```bash
PYTHONPATH=src python scripts/js_multi_live_chaos_server.py   # :8767
node scripts/js_multi_live_chaos.mjs http://127.0.0.1:8767
node scripts/js_live_chaos.mjs http://127.0.0.1:8766/         # single-script path
```

See also [CSRF_CHANNEL_HEADER.md](CSRF_CHANNEL_HEADER.md) · `BRIDGES.md` if present.
