# ADR 0011 — Delete the parallel Host≠Peer kernel (cut #4)

## Context
[ADR 0008](0008-cek-runtime-kernel-ssot.md) froze kernel SSoT as
[cek-runtime](https://github.com/bitplorer/cek-runtime).
[ADR 0009](0009-channel-cek-runtime-host-cut2.md) bound
`ChannelConfig.cek=require` to the cek-runtime Host façade
(`CekHostCapService`).
[ADR 0010](0010-channel-cek-runtime-default-cut3.md) made that the
Channel default decide.

A second decide/apply plane still lived beside that façade:

- Python `ux_channel.arch/` — `HostRuntime`, `PeerApply`, `attach_arch`,
  flow/stamps/proofs, Host-adjacent project
- Rust `HostRuntime` / `PeerApply` / `PeerRuntime` plus classic
  `Peer.mint_cap` and `POST /ux-channel/mint`

That plane was not the Cap machine after cut #3, but it was still a
second kernel. Cut #4 deletes it.

## Decision
**Cap machine = cek-runtime only.**

- `registry._caps` on `cek=require` is `CekHostCapService`
  (`kernel_ssot=cek-runtime`). No `ux_channel.arch` import is a Cap.
- `Channel.__init__` does not call `attach_arch`. Channel stays the
  product façade (wire / ASGI / UI / regions).
- EffectGraph stays L7 after Cap. `after_cek_cut2` is the Cap-gated
  project (refuse `_graph` without a present Cap; project classic-floor
  ops when a Cap is present). It is not L1.
- No local `PeerApply`. Peer apply, if needed, is a thin cek-peer wrap
  — this cut does not keep a Channel-local apply kernel.
- Classic Rust floor stays: `types` / `wire_json` / `cxb` / `actions` /
  `op_tags`. `Peer` is **verify-only** (no `mint_cap`, no
  `POST /ux-channel/mint`). Mint for demos and cross-checks is
  Channel / cek-runtime Host (or classic `CapService` when that machine
  is the test subject).
- Frozen CEK nouns only. No new product nouns. No new pyo3.

Deleted in this cut:

| Surface | Gone |
|---------|------|
| Python | entire `ux_channel.arch/` decide/apply plane |
| Rust | `host.rs`, `apply.rs`, `runtime.rs`, `registry.rs`, `effects.rs`, `flow.rs`, `project.rs`, `proof.rs`, `stamps.rs`, `drivers.rs` |
| Gate / harness | `test_arch_e2e.py`, `test_arch_properties.py`, `validate_arch_vectors.py`, `vectors/arch/`, `rust/tests/arch_vectors.rs` |
| Verify | `--cov=ux_channel.arch --cov-fail-under=80` |

## Out of scope
- Inventing nouns
- Touching cek-runtime law
- Deleting product Channel / wire / ASGI / UI / regions
- EffectGraph → L1
- Peer mint / flow-as-authority
- New pyo3
- Static `ux-peer-*.js` (client apply stays droppable)

## Consequences
One Cap machine. No second `HostRuntime`. Classic IR 0.1 without hello
still dispatches. `cek=off` remains the documented escape for tests
whose subject is classic `CapService`. Architecture law docs describe
cek-runtime SSoT; the parallel kernel is historical.
