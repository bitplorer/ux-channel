# Host kernel

Decide is **cek-runtime Host**. Channel is the product façade (wire, registry
dispatch, regions). There is no live `arch/` HostRuntime, proof, or stamps
module.

## Modules (cohesive)

| Module | Responsibility | MUST NOT |
|--------|----------------|----------|
| Cap (cek-runtime Host) | mint, verify, once consume | HTML, timers |
| Channel `CapService` | classic machine when `cek=off` | a second require Cap |
| Channel `nonce` | `use_once` for **classic** once-caps | consume on require |
| `registry` | dispatch, hooks, Cap gate order | DOM |
| `cek.effects` | EffectGraph builders (L7 after Cap) | crypto |
| `cek.project` / `after_cek_cut2` | lower graph → classic ops | I/O, Cap substitute |

Proof / stamps / `HostRuntime` lived on the deleted `arch/` plane
([ADR 0011](ADR/0011-delete-parallel-arch-kernel-cut4.md)). Historical
text: [archive/historical/proof.md](archive/historical/proof.md).

## Dispatch order (MUST)

1. Parse Intent
2. Resolve principal if configured
3. Cap gate (require and/or present-cap-must-verify)
4. once consume — **Host** on `cek=require`; Channel `nonce_store` on `cek=off`
5. Handler
6. Optional EffectGraph on the result (L7; Cap already passed)
7. `after_cek_cut2` projects `_graph` → classic-floor ops
8. Return Result

**Vector:** `python/tests/gate/test_cek_runtime_host.py` (Host-only once);
once ordering remains fail-closed ([ADR 0006](ADR/0006-once-jti-fail-closed.md)).

## Assumptions

- Handlers are app-provided and trusted for domain rules after Cap gate.
- Kernel does not interpret HTML content.
- Channel `nonce_store` on require may still exist (Redis / memory) for
  other product uses; it MUST NOT be a second once-consume machine.
