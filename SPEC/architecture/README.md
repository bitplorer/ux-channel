# Architecture extension (host kernel / peer kernel)

**Status:** kernel SSoT is [cek-runtime](https://github.com/bitplorer/cek-runtime).
The parallel `arch/` / Rust `HostRuntime` / `PeerApply` plane was deleted in
[ADR 0011](ADR/0011-delete-parallel-arch-kernel-cut4.md) (cut #4).

Classic IR 0.1 remains the permanent floor. This tree is the Channel
product (wire, caps, peers, host runtime façade) over that SSoT.
It does **not** replace `SPEC/capability.md` or `SPEC/intent-result-ops.md`.

## Design spine (do not break)

```
Intent + Cap  → truth
Result.ops    → effects only
Classic IR    → permanent floor
Cap machine   → cek-runtime Host only (Channel wrap)
flow_id       → trace (correlation, NOT authority)
Peer gate     → verify-only (no mint)
once/jti      → atomic before side effects; no store → refuse
EffectGraph   → L7 after Cap (after_cek_cut2), not L1
```

## Reading order

1. [ADR/0001-cap-only-truth.md](ADR/0001-cap-only-truth.md)
2. [ADR/0002-classic-floor.md](ADR/0002-classic-floor.md)
3. [ADR/0003-peer-kernel-no-dom.md](ADR/0003-peer-kernel-no-dom.md)
4. [ADR/0006-once-jti-fail-closed.md](ADR/0006-once-jti-fail-closed.md)
5. [ADR/0007-flow-correlation-only.md](ADR/0007-flow-correlation-only.md)
6. [ADR/0008-cek-runtime-kernel-ssot.md](ADR/0008-cek-runtime-kernel-ssot.md)
7. [ADR/0009-channel-cek-runtime-host-cut2.md](ADR/0009-channel-cek-runtime-host-cut2.md)
8. [ADR/0010-channel-cek-runtime-default-cut3.md](ADR/0010-channel-cek-runtime-default-cut3.md)
9. [ADR/0011-delete-parallel-arch-kernel-cut4.md](ADR/0011-delete-parallel-arch-kernel-cut4.md)
10. [project.md](project.md) · [proof.md](proof.md) · [flow.md](flow.md) · [budgets.md](budgets.md) · [concurrency.md](concurrency.md)
11. [peer-kernel.md](peer-kernel.md) · [host-kernel.md](host-kernel.md) · [runtime-peer.md](runtime-peer.md) · [runtime-host.md](runtime-host.md)
12. [profiles/](profiles/) · [inventory.md](inventory.md) · [non-goals.md](non-goals.md)

## Code map

| Layer | Path |
|-------|------|
| Cap machine | cek-runtime Host via `python/src/ux_channel/cek/` (`CekHostCapService`) |
| Classic Peer gate | `rust/src/peer.rs` — Intent → cap verify → demo actions (`uxc_peer`) |
| Classic floor | `rust/src/{types,wire_json,cxb,actions,op_tags,cap,nonce}.rs` |
| EffectGraph (L7) | `cek/effects.py` + `after_cek_cut2` (Cap-gated; not L1) |
| JS apply (DOM client) | `static/ux-channel.js` / `static/ux-peer-*.js` |
| Rust once/jti | `rust/src/nonce.rs` + `CapService::mint_once` / verify consume |
| Redis nonce | `ux_channel.redis_extra.RedisNonceStore` (SET NX EX, fail-closed) |

Classic clients that do not send `meta.hello` receive classic ops only.

## Tests

| Suite | What |
|-------|------|
| `python/tests/gate/test_cek_runtime_host.py` | Cap = `CekHostCapService` / `kernel_ssot=cek-runtime`; no `ux_channel.arch` |
| `python/tests/gate/test_cek_layer_honesty.py` | one Cap machine; off imports nothing |
| `rust` `cargo test --lib --tests` | classic floor + Peer verify-only |

Classic clients that omit `meta.hello` stay on flattened classic ops.
