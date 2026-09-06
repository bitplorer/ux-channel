# Effect proof (optional) — historical

> **Not live law.** The `arch/` proof / stamps plane and Rust
> `HostRuntime` / `PeerApply` were deleted in cut #4
> ([ADR 0011](../../ADR/0011-delete-parallel-arch-kernel-cut4.md)).
> Cap is cek-runtime Host + Channel façade. Kept here so older ADRs
> remain readable.

## Purpose

Host attests Result ops for a session so peer can reject forged batches. Does **not** replace Cap.

## Default opt-in

```text
proofs: "auto" | "require" | "off"
```

- `auto`: sign/verify when both sides advertise support
- `require`: refuse peers that cannot verify
- `off`: never

## Envelope (meta.effect or top-level agreed field)

```text
session_id, gen, jti, exp, body_hash, kid, sig
```

## Peer

**MUST** verify before any applyOp when proofs active for session.
Failure → apply nothing (all-or-nothing).

**Vector:** `proof/reject`

## Assumptions

- Proof private key available only on host.
- Clock skew bounded; prefer short exp.
