# Architecture extension (host kernel / peer kernel)

**Status:** implemented in this repo. Classic IR 0.1 remains the permanent floor.

This tree is the **opt-in architecture** on top of Cap 0.1 + Intent/Result/ops.
It does **not** replace `SPEC/capability.md` or `SPEC/intent-result-ops.md`.

## Design spine (do not break)

```
Intent + Cap  → truth
Result.ops    → effects only
Classic IR    → permanent floor
effects: auto | classic
proofs: auto | require | off
flow: auto | off   (meta.flow_id = correlation, NOT authority)
Peer kernel   → no DOM; drivers hold web.v1
once/jti      → atomic before side effects; no store → refuse
Cap key ≠ proof key
```

## Reading order

1. [ADR/0001-cap-only-truth.md](ADR/0001-cap-only-truth.md)
2. [ADR/0002-classic-floor.md](ADR/0002-classic-floor.md)
3. [ADR/0003-peer-kernel-no-dom.md](ADR/0003-peer-kernel-no-dom.md)
4. [ADR/0006-once-jti-fail-closed.md](ADR/0006-once-jti-fail-closed.md)
5. [ADR/0007-flow-correlation-only.md](ADR/0007-flow-correlation-only.md)
6. [project.md](project.md) · [proof.md](proof.md) · [flow.md](flow.md) · [budgets.md](budgets.md) · [concurrency.md](concurrency.md)
7. [peer-kernel.md](peer-kernel.md) · [host-kernel.md](host-kernel.md) · [runtime-peer.md](runtime-peer.md) · [runtime-host.md](runtime-host.md)
8. [profiles/](profiles/) · [inventory.md](inventory.md) · [non-goals.md](non-goals.md)

## Code map

| Layer | Path |
|-------|------|
| Host kernel | `rust/src/{cap,nonce,registry,effects,project,proof}.rs` + Python `arch/` |
| Host runtime | `rust/src/host.rs` `HostRuntime` · Python `arch/host_runtime.py` |
| Peer kernel | `rust/src/apply.rs` `PeerApply` · Python `arch/peer.py` · JS `ux-peer-kernel.js` |
| Peer runtime | `rust/src/runtime.rs` `PeerRuntime` · Python `PeerRuntime` |
| Channel attach (power) | `arch/attach.py` — `emit_graph` / `set_hello` / `grant_stamp` |
| JS apply (DOM client) | `static/ux-channel.js` — seq / timer / invoke / peerHello |
| Rust peer **gate** (classic) | `rust/src/peer.rs` — Intent → cap → demo actions (`uxc_peer`) |
| Rust once/jti | `rust/src/nonce.rs` + `CapService::mint_once` / verify consume |
| Redis nonce | `ux_channel.redis_extra.RedisNonceStore` (SET NX EX, fail-closed) |

Classic clients that do not send `meta.hello` receive classic ops only.

## Tests

`python/tests/gate/test_arch_e2e.py` — 10+ vectors on production `CapService`.
`rust` — `mint_verify_once_replay`, `PeerApply` / `PeerRuntime` / `Loopback` (peer + runtime).
