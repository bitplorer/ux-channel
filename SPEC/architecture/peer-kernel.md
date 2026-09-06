# Peer kernel

Generic apply for peers that apply Result ops. **MUST NOT** import browser
DOM APIs. There is no live Channel-local `PeerApply`.

Classic Rust `Peer` (`rust/src/peer.rs`) is **verify-only** (no mint).
JS apply lives in `static/ux-peer-kernel.js` and is droppable.

## Modules

| Module | Responsibility |
|--------|----------------|
| `hello` | Handshake claim: profiles, codecs, features (not Cap) |
| JS apply | single-flight applyResult → applyOps → applyOp |
| Classic Peer | Intent → cap verify → demo actions (`uxc_peer`) |
| `budgets` | enforce limits before walk |

## applyResult (MUST) — JS kernel

1. Enter single-flight lock (queue or reject per runtime policy).
2. Enforce budgets on ops tree.
3. applyOps.
4. Release lock.

Optional effect-proof verify lived on the deleted `arch/` plane. Historical:
[archive/historical/proof.md](archive/historical/proof.md).

## applyOp

- `seq` → applyOps(children)
- else → lookup driver method for op; if missing, ignore or strict-fail
- **MUST NOT** call ambient platform globals by string name

## Assumptions

- Drivers are registered at startup for claimed profiles only.
- Transport and X-Channel headers live in **peer runtime / transport adapter**, not kernel.
- Peer apply, if needed beyond the JS kernel, is a thin cek-peer wrap — not a
  second Channel kernel.
