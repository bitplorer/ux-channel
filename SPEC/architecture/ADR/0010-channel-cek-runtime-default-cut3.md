# ADR 0010 — Default decide is cek-runtime Host (cut #3)

## Context
[ADR 0008](0008-cek-runtime-kernel-ssot.md) froze kernel SSoT as
[cek-runtime](https://github.com/bitplorer/cek-runtime).
[ADR 0009](0009-channel-cek-runtime-host-cut2.md) bound
`ChannelConfig.cek=require` to the cek-runtime Host façade
(`CekHostCapService`). The boot default stayed `cek=off` (classic
`CapService`), and `bind_runtime_host` still attached a sibling
`RustHostKernel` that could mint beside the port Host.

Cut #4 deletes the parallel `arch/` / Rust `HostRuntime` / `PeerApply`
kernel. This cut does not.

## Decision
Default Channel decide is **cek-runtime Host**:

- `ChannelConfig.cek` field default is `require`.
- `UX_CHANNEL_CEK` default is `require`.
- Factory fallback (no config) is `require`.
- `Channel.boot` without an explicit `cek=` uses the cek-runtime Host
  façade on `registry._caps` — not `arch` `HostRuntime`, not
  `attach_arch`.
- `attach_arch` stays the L7 stamps / flow / EffectGraph plane.
  It does not mint or verify Caps.
- One mint / verify owner: documented port `cek_host.Host`.
  `RustHostKernel` / `CEK_BIN` is runtime reachability only
  (`host-json` is a fresh Host per call).
- Bare install without `cek-host` / `cek-surface` fails closed.
  Explicit escape: `cek=off` or `UX_CHANNEL_CEK=off`.
- EffectGraph stays L7 after Cap (`after_cek_cut2`).
- Frozen CEK nouns only. No new product nouns.

`cek=off` still imports nothing and keeps classic `CapService` for
tests whose subject is that machine.

## Out of scope
- Deleting `arch/` / Rust `HostRuntime` / `PeerApply` (cut #4)
- EffectGraph into L1
- Inventing nouns
- Peer mint / flow-as-authority
- New pyo3

## Consequences
Default boot Cap authority is the cek-runtime Host façade.
Classic IR 0.1 without hello still dispatches. `cek=off` remains the
documented escape. Parallel kernel stays bootable until cut #4.
