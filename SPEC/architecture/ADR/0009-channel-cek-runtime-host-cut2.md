# ADR 0009 — Channel Cap machine is cek-runtime Host (cut #2)

## Context
[ADR 0008](0008-cek-runtime-kernel-ssot.md) froze kernel SSoT as
[cek-runtime](https://github.com/bitplorer/cek-runtime). Channel still shipped
an optional `[cek]` drop-in that treated **cek-host `Host` / cek-surface** as
if they *were* the kernel.

Cut #1 (peer apply budgets) lands in cek-runtime, not here.

## Decision
`ChannelConfig.cek=require` Cap machine is **cek-runtime Host**:

- Preferred wrap: `cek_host.rust_wrap.RustHostKernel` → `cek host-json`
  (`CEK_BIN` must be the runtime binary, not `cek-host`'s console script).
- Else the documented language port: `cek_host.Host` (stateful mint / verify /
  once / sealed-args). `host-json` is a fresh Host per call, so Channel tokens
  stay on the port.
- `cek_surface` remains Continuation compose only — not a kernel.
- Façade shape (`CekHostCapService`) is unchanged. One Cap owner on require.
- `cek=off` still imports nothing.

Encoding maps (frozen CEK nouns only):

| Channel | CEK | Law |
|---------|-----|-----|
| `flow_id` | `trace` | correlation only (ADR 0007 / LAW §10) |
| hello | Profile + Manifest | handshake; Manifest **never** grants Cap |
| stamp | handshake apply-set | not a Cap |

EffectGraph is **L7** pre-project **after Cap** (not L1). `arch/` /
HostRuntime / PeerApply stay bootable and are **not** the Cap machine.

No new pyo3. No Peer mint. No flow-as-authority.

## Out of scope
- Deleting `arch/` / Rust `HostRuntime` / `PeerApply` (later cut)
- EffectGraph into L1
- Inventing nouns
- Peer mint / flow-as-authority

## Consequences
`[cek]` is a Channel adapter over cek-runtime Host, not a second SSoT.
Classic IR 0.1 without hello still dispatches. Oracle / drop-in parity stay
on the port Host token.
