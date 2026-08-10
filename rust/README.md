# ux_channel_rs — Rust peer (Phase 2)

**Status:** types + JSON wire + **cap verify** + **CXB** + **HTTP action endpoint** + `uxc_check`.

Operators: read repo-root [`OPERATIONAL.md`](../OPERATIONAL.md) before running `uxc_peer`.
Humans: [`TERMINOLOGY.md`](../TERMINOLOGY.md) → [`HOW_IT_WORKS.md`](../HOW_IT_WORKS.md) → [`REFERENCE.md`](../REFERENCE.md) / [`FAQ.md`](../FAQ.md).

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
| `bin/uxc_check` | Vectors + cap + CXB + peer edges + optional `--http` | moving surface, permanent duty |
| `bin/uxc_peer` | HTTP peer: `POST /ux-channel/action` + demo UI | **moving** |

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
  "policy": { "present_cap_must_verify": true, "once_jti_enforced": false }
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
5. once/jti: **not enforced** in Cap 0.1 (health: `once_jti_enforced: false`)

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

- [ ] once/jti consumption + tests
- [ ] HTTP Accept `+cxb` response path
- [ ] Byte-identical encode vs Python oracle freeform
- [ ] WASM island / mesh (later phases)
