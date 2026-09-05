# Channel `[cek]` adapter (cut #4)

Kernel SSoT is **[cek-runtime](https://github.com/bitplorer/cek-runtime)** —
[ADR 0008](../../../../SPEC/architecture/ADR/0008-cek-runtime-kernel-ssot.md).
This package is a Channel wrap, not a second kernel.

Default decide is **`cek=require`**
([ADR 0010](../../../../SPEC/architecture/ADR/0010-channel-cek-runtime-default-cut3.md)).
Cut #4 deleted the parallel `arch/` / `HostRuntime` / `PeerApply` plane
([ADR 0011](../../../../SPEC/architecture/ADR/0011-delete-parallel-arch-kernel-cut4.md)).

| Mode | Cap machine | Imports |
|------|-------------|---------|
| `require` (default) | **cek-runtime Host** via `CekHostCapService` | `cek-host` + `cek-surface` |
| `adapt` | Channel `CapService` (cek Host on the side) | `cek-host` + `cek-surface` |
| `off` | Channel `CapService` | none (explicit escape) |

**require wrap — one mint / verify owner**

1. Documented port Host: `cek_host.Host` (stateful mint / verify / once /
   sealed-args). This is the only Cap machine on `registry._caps`.
2. `CEK_BIN` / `RustHostKernel` → `cek host-json` is runtime reachability,
   not a second mint path (`host-json` is a fresh Host per call).
   `CEK_BIN` must be the **runtime** `cek` binary (not `cek-host`'s
   console script). No new pyo3.

`cek_surface` = Continuation compose only.

Bare install without the wrap packages: set `cek=off` or `UX_CHANNEL_CEK=off`.

**Encodings** (`encode.py`) — frozen CEK nouns only:

- `flow_id` → `trace` (correlation; ADR 0007)
- hello → Profile / Manifest (handshake; Manifest never grants Cap)
- stamp → handshake apply-set (not a Cap)

**EffectGraph** is L7 pre-project after Cap (`after_cek_cut2` +
`cek.effects.project_graph`). Not L1. No `ux_channel.arch`. No second
`HostRuntime`. Peer is verify-only.

See [ADR 0009](../../../../SPEC/architecture/ADR/0009-channel-cek-runtime-host-cut2.md),
[ADR 0010](../../../../SPEC/architecture/ADR/0010-channel-cek-runtime-default-cut3.md),
and [ADR 0011](../../../../SPEC/architecture/ADR/0011-delete-parallel-arch-kernel-cut4.md).
