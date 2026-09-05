# Python → Rust forward (P2d)

Minimal adapter: host Python mints a classic-floor cap, POSTs one
hot action (`Cart.add`) to the Rust peer (verify-only), and returns **Result.ops unchanged**.

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
cd rust
UXC_ALLOW_ORACLE_SECRET=1 UXC_PORT=8787 cargo run --bin uxc_peer

# terminal B — forward one action
python3 demos/python_forward/forward_to_rust.py --base http://127.0.0.1:8787
```

| Flag | Default | Meaning |
|------|---------|---------|
| `--base` | `http://127.0.0.1:8787` | Peer base URL |
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
