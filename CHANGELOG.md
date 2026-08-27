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

---
