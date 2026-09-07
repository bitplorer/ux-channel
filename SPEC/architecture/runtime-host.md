# Host runtime

Channel is the **product host** (boot, registry, regions, ASGI). The Cap
machine on `cek=require` (default) is **cek-runtime Host** via the Channel
façade `CekHostCapService`. There is no live `HostRuntime` module.

## Responsibilities

- Load config; **MUST** refuse oracle/demo secret unless `demo_mode: true`
- Dispatch Intent → Cap gate → handler → Result
- Once consume on require: **Host only** (`cek_host.Host` /
  `MemoryOnceBackend`). Channel `nonce_store` is not re-consumed.
- Classic `CapService` + Channel `nonce_store` remain for `cek=off`
- Health / diagnose: `once_jti_enforced` is true when Host owns once
  (require) or when a Channel nonce store is present (classic)
- `previous_secrets` rotation is **classic CapService (`cek=off`) only**.
  cek-host Host has no HMAC previous_secrets API. `cek=require` refuses
  a non-empty window (cut #5D). Diagnose reports `verify: unwired`.

## Config (documented defaults)

```text
demo_mode: false
require_cap: true          # prod writes
cek: require               # Cap machine = cek-runtime Host (ADR 0010)
effects: "auto"            # or "classic" — EffectGraph is L7 after Cap
trace: "auto"              # CEK correlation (VOCAB); never authority
flow: "auto"               # alias of trace (env FLOW; wire meta.flow_id)
nonce_store: Channel store for cek=off once-caps; unused for require consume
```

## Code

| Language | Path |
|----------|------|
| Python host | `python/src/ux_channel/host/` — Channel, registry, factory |
| Cap façade | `python/src/ux_channel/cek/host_adapter.py` — `CekHostCapService` |
| Cap machine | cek-runtime Host (`cek_host.Host`) |
| Rust | `rust/src/peer.rs` — classic demo gate (verify-only). No `HostRuntime`. |

A Rust **Channel** (regions / ASGI) is out of scope. Mint for demos and
cross-checks is Channel / cek-runtime Host (or classic `CapService` when
that machine is the test subject).

## Assumptions

- HTTP framework (FastAPI, etc.) is an adapter calling `registry.dispatch`.
- App registers handlers on the registry before serve.
- EffectGraph / hello Profile·Manifest are not a second Cap machine.
