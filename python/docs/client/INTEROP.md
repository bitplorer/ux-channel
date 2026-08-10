# Interop — uxchannel 0.1

| Stack | Integration |
|-------|-------------|
| **FastAPI** | `Channel.boot(app, …)` — [FASTAPI.md](../asgi/FASTAPI.md) |
| **Starlette** | `mount_channel_starlette` |
| **ux-dom** | optional **`ux_channel_ux_dom`** glue — never inside core `uxchannel` or `ux_dom` |
| **ux-dom (manual)** | `raw(region())`, `ch.control(…).as_ux_dom()` |
| **Jinja / plain HTML** | `ch.html` + `ch.control(…).as_dict()` attrs |
| **HTMX** | Complementary; channel owns Intent/Result, not hx-* |
| **Datastar / other** | Can consume morph HTML; channel still owns actions |
| **Redis** | Optional nonce, rate, state, push |


See `MOAT.md` for layering of capability / morph IR / sealed bridges.
