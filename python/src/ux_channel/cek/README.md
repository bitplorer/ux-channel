# Channel `[cek]` adapter (cut #2)

Kernel SSoT is **[cek-runtime](https://github.com/bitplorer/cek-runtime)** —
[ADR 0008](../../../../SPEC/architecture/ADR/0008-cek-runtime-kernel-ssot.md).
This package is a Channel wrap, not a second kernel.

| Mode | Cap machine | Imports |
|------|-------------|---------|
| `off` | Channel `CapService` | none |
| `adapt` | Channel `CapService` (cek Host on the side) | extra `[cek]` |
| `require` | **cek-runtime Host** via `CekHostCapService` | extra `[cek]` |

**require wrap**

1. `cek_host.rust_wrap.RustHostKernel` → `cek host-json` when `CEK_BIN` is the
   **runtime** `cek` binary (not `cek-host`'s console script).
2. Else documented port Host: `cek_host.Host` (stateful mint / verify / once /
   sealed-args). No new pyo3.

`cek_surface` = Continuation compose only.

**Encodings** (`encode.py`) — frozen CEK nouns only:

- `flow_id` → `trace` (correlation; ADR 0007)
- hello → Profile / Manifest (handshake; Manifest never grants Cap)
- stamp → handshake apply-set (not a Cap)

**EffectGraph** is L7 pre-project after Cap (`after_cek_cut2`). Not L1.

`arch/` / HostRuntime / PeerApply stay bootable and are **not** the Cap
machine. See [ADR 0009](../../../../SPEC/architecture/ADR/0009-channel-cek-runtime-host-cut2.md).
