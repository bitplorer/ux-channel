## 2026-08-31 — Door H: closed core, four doors

- Browser runtime is a closed core. Python (or a driver) mints `Result.ops[]`.
  JS only applies. New client behaviour enters through doors, not new
  `applyOp` cases: `registerOp`, `on` (beforeApply / beforeOp / afterOp /
  afterApply), `configure` (existing error-plane knobs), `uxBridge.register`.
- Client bag is `uxChannel.signals`, written only by `signal.set`.
  No `store` alias.
- Persist is the existing Python flag: `st.client(..., persist=True)` after
  `state(ch, allow=[...])`. JS writes `localStorage["channel:sig:"+path]`
  and silently hydrates that prefix on boot (`SIG_PREFIX.length`, not
  `slice(8)`). No hydrate / restore-focus body attrs or configure knobs.
- Morph focus/scroll restore stays always-on. It is not persist.
- Docs: `docs/reference/client-runtime.md`, EXTENSIONS Door H, LONGEVITY
  Door H, `python/docs/client/JS_RUNTIME.md`, FEATURES §4.1 / §6,
  `python/docs/state/STATE.md` (dead `PLANES.md` link → state-planes),
  `python/docs/ts-client.stub.d.ts` (`registerOp`, `signals`).
- Test: `test_js_runtime_multi_load.py::test_client_runtime_doors`.
- Python `ClientPlane` / persist minting unchanged.

---

## 2026-08-28 — Live field latest-wins

- `input` / `change` on the same control abort the in-flight Intent
  (AbortController already on `postIntent`). Replaced Results do not
  morph and do not toast timeout. Click / swipe / longpress still drop
  while in-flight.
- Docs: JS_RUNTIME live fields. Test: `test_js_live_field_last_wins.py`.

---

## 2026-08-27 — Signal → Intent

- Client: `data-channel-on` grammar (`delay:`, `threshold:`, `throttle:`, `once`).
- Signals: click, change, input, blur, longpress, swipe.*; synth horizontal|vertical.
- Form attach on control signals; inherit on/target.
- No `data-channel-swipe*` / `on-debounce` / `on-threshold` attribute families.
- Docs: `python/docs/client/JS_RUNTIME.md`, `python/docs/FEATURES.md` §1.3b.

---

## 2026-08-15 — Enhance runtime wiring

- `enhance/attach.py` — HandshakeRegistry + SessionRecorder façade on Channel
- `enhance/asgi_wire.py` — pure helpers for hello + post-dispatch project
- `asgi/enhance_routes.py` — `POST {path}/hello` without editing core fastapi.py
- `Channel.boot` attaches enhance plane (opt-out: `config.enhance=False`)
- `ch.enhance.mint_continuation` mints real attenuated Caps
- Gate: `python/tests/gate/test_enhance_runtime.py` (8 passed)
- Classic IR 0.1 clients unchanged

---

## 2026-08-15 — Enhance plane activation

- Host handshake: `HandshakeRegistry` / `PeerSession` project Result.ops via PeerHello surfaces
- Real DOM drivers: `static/ux-peer-dom-drivers.js`
- Demo: `demos/enhance_search/`
- Waves A–G remain additive; classic IR 0.1 unchanged
