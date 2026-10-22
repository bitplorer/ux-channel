<!-- pyramid -->
Read [../../../START_HERE.md](../../../START_HERE.md) first if you are new. This is Layer 2 (encyclopedia), not the intro.

# Plugins & bridges — uxchannel 0.1

## Host adapters

- `ux_channel.asgi.fastapi.FastAPIHostAdapter` / `mount_channel`
- `ux_channel.asgi.starlette` — Starlette mount

Registered via plugin hub when using `create_channel(..., host="fastapi")`.

## npm bridges

For third-party JS widgets (charts, maps):

1. SSR a host node with `mount_html` from `ux_channel.bridge_api`
   (`mount_html(bridge_id, package=…, props=…)`)  
2. Load `ux-bridge.js`: `ch.runtime(bridge=True)` (or `demo_page(..., bridge=True)`).
   It is off by default.  
3. Drive with `bridge_mount` / `bridge_update` / `bridge_call` / `bridge_destroy` ops  

This is **not** the same as a **region** morph slot.
