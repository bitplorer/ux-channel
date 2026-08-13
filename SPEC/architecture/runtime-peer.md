# Peer runtime

## Responsibilities

- Start with chosen profiles and driver packs
- Send hello to host (when transport supports)
- `submit_intent(action, args, cap, request_id?)`
- On Result: enqueue `kernel.applyResult`
- Optional outbox (explicit opt-in)
- Local revoke / re-hello → gen++

## Code

| Language | Path |
|----------|------|
| Python | `python/src/ux_channel/arch/peer.py` — `PeerRuntime` |
| Rust | `rust/src/runtime.rs` — `PeerRuntime` + `Loopback` / `Outbox` |
| JS | `static/ux-peer-kernel.js` — `onResult` / `hello` / `bumpGen` |

Transport (HTTP, loopback, outbox) is an adapter. The kernel never speaks X-Channel headers or DOM.

## Assumptions

- Browser page or agent process provides the event loop.
- Click wiring and tool loops are **shell** code, not kernel.
