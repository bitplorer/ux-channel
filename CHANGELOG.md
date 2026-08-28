## 2026-08-28 — Live field settle

- `input` / `change` abort in-flight on the keystroke itself, not only
  when the debounced fire runs. Empty value fires now so a clear does
  not keep a stale listing.
- Docs: JS_RUNTIME live fields. Test: `test_js_live_field_last_wins.py`.

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
