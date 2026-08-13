# Host runtime

## Responsibilities

- Load config; **MUST** refuse oracle/demo secret unless `demo_mode: true`
- Open nonce and idempotency stores
- Session map: `session_id → { gen, peer_hello, stamps? }`
- `handle_intent(raw, conn_ctx) -> Result`
- `revoke_session(session_id)` → gen++
- Health: stores_ok, demo_mode, key kids

## Config (documented defaults)

```text
demo_mode: false
require_cap: true          # prod writes
effects: "auto"            # or "classic"
proofs: "auto"             # or "require" | "off"
flow: "auto"               # or "off"
nonce_store: required if once Caps used
```

## Code

| Language | Path |
|----------|------|
| Python | `python/src/ux_channel/arch/host_runtime.py` — `HostRuntime` |
| Rust | `rust/src/peer.rs` — inbound **gate** (Intent → cap → dispatch). Not a full Channel host. |

A Rust Channel (regions / ASGI) is out of scope. The Rust **peer gate** plus **peer runtime** is the architecture pair.

## Assumptions

- HTTP framework (FastAPI, etc.) is an adapter calling `handle_intent`.
- App registers handlers on the registry before serve.
