## 2026-08-15 — Enhance runtime wiring

- `python/src/ux_channel/enhance/attach.py` — HandshakeRegistry + SessionRecorder façade on Channel
- `python/src/ux_channel/enhance/asgi_wire.py` — pure helpers for hello + post-dispatch project
- `python/src/ux_channel/asgi/enhance_routes.py` — `POST {path}/hello` without editing core fastapi.py
- `ch.enhance.mint_continuation` mints real attenuated Caps
- Gate: `python/tests/gate/test_enhance_runtime.py`
- Classic IR 0.1 clients unchanged
- **Before merge:** run `scripts/RESTORE_CHANNEL.sh` (or checkout channel.py from main + apply enhance attach block)

---

## 2026-08-15 — Enhance plane activation

- Host handshake: `HandshakeRegistry` / `PeerSession` project Result.ops via PeerHello surfaces
- Real DOM drivers: `static/ux-peer-dom-drivers.js` (shadow, pending, morph/toast helpers)
- Demo: `demos/enhance_search/` — coalesce + continuation + perception (no backend)
- Waves A–G remain additive; classic IR 0.1 unchanged

---
