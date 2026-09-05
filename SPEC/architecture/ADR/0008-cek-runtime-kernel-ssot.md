# ADR 0008 — Kernel SSoT is cek-runtime

## Context
This repo still ships a parallel host/peer kernel (`python/src/ux_channel/arch/`, Rust `HostRuntime` / `PeerApply`) next to the product surface (Channel, wire, caps). Kernel work must not fork further.

This is **not** the optional Channel `cek` extra (Cap drop-in). Kernel SSoT is the **cek-runtime** repo.

## Decision
Kernel single source of truth is **[bitplorer/cek-runtime](https://github.com/bitplorer/cek-runtime)**.

Freeze **new** kernel work in:

- `python/src/ux_channel/arch/`
- Rust `HostRuntime` (`rust/src/host.rs`)
- Rust `PeerApply` (`rust/src/apply.rs`)

Product surface remains in scope here: Channel, wire, caps.

**Green cut #1** (lands in cek-runtime, not this repo): Peer apply budgets.

## Out of scope
- EffectGraph / `flow` / Peer mint lift
- Channel → cek-runtime adapter (cut #2)
- Deleting the parallel kernel (later)

This ADR does not rewrite adapters and does not delete `arch/` / HostRuntime / PeerApply.

## Consequences
New kernel law and apply-budget work go to cek-runtime. Channel product work continues here. Existing parallel kernel stays until a later cut.
