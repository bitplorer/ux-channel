# ux_channel_rs — Rust kernel + runtime

**Status:** host kernel+runtime + peer kernel+runtime + classic IR 0.1 gate + cap/once/jti + CXB + `uxc_check`.

The crate is still the **Rust product package**. It is not “just a demo peer.”

| Role | Type | File |
|------|------|------|
| Host kernel + runtime | `HostRuntime` | `src/host.rs` |
| Peer kernel (no DOM) | `PeerApply` | `src/apply.rs` |
| Peer runtime | `PeerRuntime` | `src/runtime.rs` |
| Classic demo gate | `Peer` | `src/peer.rs` → `uxc_peer` |

Operators: read repo-root [`OPERATIONAL.md`](../OPERATIONAL.md) before running `uxc_peer`.
Humans: [`TERMINOLOGY.md`](../TERMINOLOGY.md) → [`HOW_IT_WORKS.md`](../HOW_IT_WORKS.md) → [`REFERENCE.md`](../REFERENCE.md) / [`FAQ.md`](../FAQ.md).
Law: [`SPEC/architecture/`](../SPEC/architecture/).

## What works

| Module / binary | Role | Class |
|-----------------|------|--------|
| `types` | `Intent`, `ResultDoc`, `Op`, `ErrorObject`, `Trace`, `Hop` | permanent |
| `wire_json` | encode/decode + canonical JSON + validation | permanent |
| `cap` | itsdangerous-compatible mint/verify (oracle secret + args_hash) | permanent API; oracle = test-only |
| `cxb` | CXB1/CXBZ encode/decode (decode matches frozen oracle blobs) | permanent tags; encode freeform still evolving |
| `op_tags` | Dense op key tags 1–63 (append-only) | permanent |
| `actions` | `Cart.add`, `Counter.inc`, `Counter.get` | **moving** demo |
| `peer` | Intent → cap gate → dispatch → Result (always Result-shaped) | permanent gate |
| `host` | Host kernel+runtime: `HostRuntime` (project, proofs, flow, registry, sessions) | permanent |
| `effects` / `project` | EffectGraph builders + pure project(auto\|classic) | permanent |
| `runtime` | `PeerRuntime`: hello, submit_intent, on_result, revoke + `Loopback` | permanent |
| `proof` | HMAC-SHA256 effect proofs (Cap key ≠ proof key) | permanent |
| `drivers` | web.v1 / agent.v1 log packs; `safe_href` | permanent |
| `bin/uxc_check` | Vectors + cap + CXB + peer edges + optional `--http` | moving surface, permanent duty |
| `bin/uxc_peer` | HTTP peer: `POST /ux-channel/action` + demo UI | **moving** |

## Layout

```text
rust/
├── Cargo.toml
├── README.md
├── src/
│   ├── lib.rs           # crate root re-exports
│   ├── types.rs         # Intent, ResultDoc, Op (IR)
│   ├── wire_json.rs     # JSON encode/decode + canonical_json
│   ├── cap.rs           # CapService mint/verify/hash_args
│   ├── cxb.rs           # CXB codec
│   ├── op_tags.rs       # dense op tags (append-only)
│   ├── peer.rs          # classic Intent → cap gate → demo actions
│   ├── host.rs          # HostRuntime (kernel + runtime)
│   ├── effects.rs       # EffectGraph builders
│   ├── project.rs       # pure project(auto|classic)
│   ├── registry.rs      # present-cap-must-verify dispatch
│   ├── apply.rs         # PeerApply kernel (no DOM)
│   ├── runtime.rs       # PeerRuntime + Loopback / Outbox
│   ├── proof.rs         # effect proofs
│   ├── flow.rs          # flow_id correlation only
│   ├── stamps.rs        # invoke stamps
│   ├── drivers.rs       # web.v1 / agent.v1 (no DOM)
│   ├── actions.rs       # demo actions (moving)
│   └── bin/
│       ├── uxc_check.rs # conformance runner
│       └── uxc_peer.rs  # HTTP demo peer
└── tests/
    ├── integration_peer.rs
    └── arch_vectors.rs   # SPEC project fixtures
```

**Permanent vs moving:** types/wire/cap/cxb/host/project/apply/runtime/proof/drivers/peer-gate are permanent; `actions` + `uxc_peer` UI are demo/moving.


## Tests

| Kind | Command | What |
|------|---------|------|
| Unit + property | `cargo test --lib` | cap, wire, peer, apply, runtime, CXB + proptest |
| Integration | `cargo test --tests` | Classic gate + `arch_vectors` (project fixtures) |
| Conformance | `cargo run --bin uxc_check -- ../conformance` | golden vectors |

Property invariants (proptest):

* `hash_args` deterministic, 32 hex chars  
* mint → verify roundtrip for arbitrary action/args  
* tampered args → `ArgsMismatch`  
* wrong action → `ActionMismatch`  
* intent JSON encode/decode roundtrip  

## Build & check

```bash
cd rust
cargo test --lib
cargo build --bins

cargo run --bin uxc_check -- ../conformance

# Live HTTP peer (demo secret only)
UXC_ALLOW_ORACLE_SECRET=1 UXC_PORT=8787 cargo run --bin uxc_peer &
cargo run --bin uxc_check -- ../conformance --http http://127.0.0.1:8787
```

**Production:**

```bash
export UXC_CAP_SECRET='your-private-high-entropy-secret'
# do NOT set UXC_ALLOW_ORACLE_SECRET
cargo run --bin uxc_peer
```

Expected check output: `All checks passed`.

## HTTP surface

| Method | Path | Body | Notes |
|--------|------|------|-------|
| `POST` | `/ux-channel/action` | Intent JSON | Cap verified when required / present |
| `GET`  | `/ux-channel/health` | — | Honest advertisement (see below) |
| `POST` | `/ux-channel/mint` | `{action,args,sub?,scopes?}` | Mint with the **same** secret as the verifier; protect in production |
| `GET`  | `/` | — | Interactive demo page |

Default bind: `0.0.0.0:8787` (`UXC_HOST` / `UXC_PORT`).

### Secret policy (fail closed)

| Situation | Behavior |
|-----------|----------|
| `UXC_CAP_SECRET` private ≥ 16 chars | Starts; `demo_mode: false` |
| Secret unset / empty / equals public oracle | **Refuses** unless `UXC_ALLOW_ORACLE_SECRET=1` |
| Allow-listed oracle | Starts with loud stderr WARNING; `demo_mode: true` |

### Health honesty

```json
{
  "formats": ["application/ux-channel+json"],
  "codecs": ["json", "cxb"],
  "demo_mode": true,
  "http": { "action": { "content_type": "application/ux-channel+json", "...": "..." } },
  "cap_required": ["Cart.add"],
  "policy": { "present_cap_must_verify": true, "once_jti_enforced": true }
}
```

- `formats` / `http` = what the HTTP endpoint actually serves today  
- `codecs` = what the peer library can encode/decode (CXB is library-ready; Accept negotiation not on `/action` yet)
- `demo_mode` = running with public/allow-listed oracle secret  
- HTTP status on action: `200` if `ok`, `401` if `unauthorized`, else `400` for Result errors (body still rules)

### Cap policy

1. `Cart.add` always requires a valid cap → `unauthorized` / “capability token required” if missing  
2. Any Intent that includes `cap` must verify (open actions cannot carry a bogus cap and proceed)  
3. Morph HTML **and** toast display text escape free-form strings; `signal_set` keeps raw semantic values  
4. Integer args (`qty`, `by`) reject non-integers (no silent coercion)  
5. once/jti: **enforced** (`mint_once` + `MemoryNonceStore`; health: `once_jti_enforced: true`)

Wire/parse failures return a Result `{ ok:false, error, meta }` — never a bare non-IR body.

### Error codes (this peer)

| Code | Typical cause |
|------|----------------|
| `unauthorized` | Missing / bad / mismatched / expired cap |
| `validation` | IR version, type coercion, domain field rules |
| `not_found` | Unknown action or HTTP route |
| `internal` | Encode failure or cap payload construction failure |

## Cap compatibility

Matches Python `CapService` / `itsdangerous.URLSafeTimedSerializer`:

- salt `ux-channel-cap`
- django-concat key derivation + HMAC-SHA1
- URL-safe base64, optional zlib payload
- timed signature + `max_age`
- `args_hash = sha256(compact sorted JSON)[:32 hex]`

Oracle vector: `conformance/vectors/cap/02-oracle-token.json`.

## CXB

- Module: `src/cxb.rs` (+ `op_tags.rs`)
- Frozen blobs: `conformance/expected/cxb/`
- `uxc_check` decodes every blob and runs structural re-encode
- Freeform map key order may differ from Python msgpack → encode sha256 not yet byte-identical

## Python forward

See [`../demos/python_forward/`](../demos/python_forward/) — host mints (or asks peer to mint), POSTs `Cart.add`, returns `Result.ops` unchanged.  
Parses Result bodies from HTTP 4xx (peer keeps Result shape on 401/400).

## Layout

```text
src/
  lib.rs
  types.rs       PERMANENT
  wire_json.rs   PERMANENT
  cap.rs         PERMANENT API (oracle = test-only constant)
  cxb.rs         PERMANENT tags
  op_tags.rs     PERMANENT
  peer.rs        PERMANENT gate
  actions.rs     MOVING demo domain
  bin/uxc_check.rs
  bin/uxc_peer.rs
```

## Next

- [x] once/jti consumption + tests
- [x] peer kernel (`PeerApply`) + peer runtime (`PeerRuntime` / `Loopback`)
- [x] host kernel + host runtime (`HostRuntime` / project / registry)
- [ ] HTTP Accept `+cxb` response path
- [ ] Byte-identical encode vs Python oracle freeform
- [ ] WASM island / mesh (later phases)


## Python parity (same law)

| Concern | Rust | Python |
|---------|------|--------|
| Cap mint/verify | `CapService::mint` / `verify` | `CapService.mint` / `verify` |
| args_hash | sorted compact JSON | same (`sort_keys=True`) |
| CXB decode | `decode_cxb` | `wire.cxb.decode_cxb` |
| Conformance | `uxc_check` | `conformance/harness/*` + gate tests |
| Peer gate | `peer::Peer` | demo `uxc_peer` (not HostRuntime) |
| Host kernel + runtime | `host::HostRuntime` | `arch.HostRuntime` |
| Peer kernel | `apply::PeerApply` | `arch.peer.PeerApply` |
| Peer runtime | `runtime::PeerRuntime` | `arch.peer.PeerRuntime` |
| Effect proofs | `proof::ProofService` | `arch.proof.ProofService` |
| Project | `project::project` | `arch.project` |
| Full host (regions/ASGI) | — | `ux_channel` Channel |

See [MENTAL_MODEL.md](../MENTAL_MODEL.md) and [NAMING.md](../NAMING.md).
