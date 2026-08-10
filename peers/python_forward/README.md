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
# terminal A — Rust peer (demo secret — see OPERATIONAL.md)
cd peers/ux_channel_rs
UXC_ALLOW_ORACLE_SECRET=1 UXC_PORT=8787 cargo run --bin uxc_peer

# terminal B — forward one action
python3 peers/python_forward/forward_to_rust.py --base http://127.0.0.1:8787
# or mint via Rust if itsdangerous is unavailable:
python3 peers/python_forward/forward_to_rust.py --mint-via-peer --sku abc-123 --qty 2
```

| Flag | Default | Meaning |
|------|---------|---------|
| `--base` | `http://127.0.0.1:8787` | Peer base URL |
| `--mint-via-peer` | off | Mint via `POST /ux-channel/mint` |
| `--sku` | `abc-123` | Cart sku |
| `--qty` | `2` | Cart qty (integer) |

Exit code `0` only when `result.ok` is true.  
Unauthorized / validation still print a Result body (HTTP 4xx is parsed).

## Principles held

1. One IR — no parallel RPC  
2. JSON floor  
3. Caps travel on the Intent  
4. Peers > FFI (HTTP, not PyO3 for business logic)  
5. Ops are never rewritten by the forward adapter  

## See also

- [`../../TERMINOLOGY.md`](../../TERMINOLOGY.md)
- [`../../HOW_IT_WORKS.md`](../../HOW_IT_WORKS.md)
- [`../../REFERENCE.md`](../../REFERENCE.md) §7
- [`../../OPERATIONAL.md`](../../OPERATIONAL.md)
- [`../../FAQ.md`](../../FAQ.md)
