# Python → Rust forward (P2d)

Minimal adapter: host Python mints (or asks Rust to mint) a cap, POSTs one
hot action (`Cart.add`) to the Rust peer, and returns **Result.ops unchanged**.

```text
client / host
    │  Intent { action, args, cap }
    ▼
python_forward/forward_to_rust.py
    │  HTTP POST application/ux-channel+json
    ▼
uxc_peer  (Rust)  ── cap verify ──► Cart.add ──► Result { ok, ops[] }
    │
    ▼
ops[] returned as-is to the client
```

## Run

```bash
# terminal A — Rust peer
cd peers/ux_channel_rs
UXC_PORT=8787 cargo run --bin uxc_peer

# terminal B — forward one action
python3 peers/python_forward/forward_to_rust.py --base http://127.0.0.1:8787
# or mint via Rust if itsdangerous is unavailable:
python3 peers/python_forward/forward_to_rust.py --mint-via-peer
```

Exit code `0` only when `result.ok` is true.

## Principles held

1. One IR — no parallel RPC  
2. JSON floor  
3. Caps travel on the Intent  
4. Peers > FFI (HTTP, not PyO3 for business logic)  
5. Ops are never rewritten by the forward adapter

## See also

- [`../../HOW_IT_WORKS.md`](../../HOW_IT_WORKS.md)
- [`../../OPERATIONAL.md`](../../OPERATIONAL.md)

