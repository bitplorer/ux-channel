# Peer runtime

## Responsibilities

- Start with chosen profiles and driver packs
- Send hello to host (when transport supports) — handshake, not Cap
- `submit_intent(action, args, cap, request_id?)`
- On Result: enqueue JS kernel `applyResult` when the client apply is loaded
- Local revoke / re-hello → gen++

There is no live Python/Rust `PeerRuntime` / `PeerApply`. Classic Rust
`Peer` is verify-only. JS apply is droppable.

## Code

| Language | Path |
|----------|------|
| JS | `static/ux-peer-kernel.js` — `onResult` / `hello` / `bumpGen` |
| Classic Rust gate | `rust/src/peer.rs` — Intent → cap verify → demo actions |
| Channel HTTP | `python/src/ux_channel/asgi/` — transport adapter |

Transport (HTTP, loopback, outbox) is an adapter. The kernel never speaks X-Channel headers or DOM.

## Assumptions

- Browser page or agent process provides the event loop.
- Click wiring and tool loops are **shell** code, not kernel.
