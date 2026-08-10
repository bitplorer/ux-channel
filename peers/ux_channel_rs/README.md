# ux_channel_rs — Rust peer (Phase 2)

**Status:** types + JSON wire + **cap verify** + **CXB** + **HTTP action endpoint** + `uxc_check`.

## What works

| Module / binary | Role |
|-----------------|------|
| `types` | `Intent`, `ResultDoc`, `Op`, `ErrorObject`, `Trace`, `Hop` |
| `wire_json` | encode/decode + canonical JSON + validation |
| `cap` | itsdangerous-compatible mint/verify (oracle secret + args_hash) |
| `cxb` | CXB1/CXBZ encode/decode (decode matches frozen oracle blobs) |
| `op_tags` | Dense op key tags 1–63 (append-only) |
| `actions` | `Cart.add`, `Counter.inc`, `Counter.get` |
| `peer` | Intent → cap gate → dispatch → Result (always Result-shaped) |
| `bin/uxc_check` | Vectors + cap + CXB + peer edges + optional `--http` |
| `bin/uxc_peer` | HTTP peer: `POST /ux-channel/action` + demo UI |

## Build & check

```bash
cd peers/ux_channel_rs
cargo test --lib
cargo build --bins

cargo run --bin uxc_check -- ../../conformance

# With live HTTP peer
UXC_PORT=8787 cargo run --bin uxc_peer &
cargo run --bin uxc_check -- ../../conformance --http http://127.0.0.1:8787
```

Expected: `All checks passed`.

## HTTP surface

| Method | Path | Body | Notes |
|--------|------|------|-------|
| `POST` | `/ux-channel/action` | Intent JSON | Cap verified when required / present |
| `GET`  | `/ux-channel/health` | — | Honest advertisement (see below) |
| `POST` | `/ux-channel/mint` | `{action,args,sub?,scopes?}` | Dev mint (oracle secret) |
| `GET`  | `/` | — | Interactive demo page |

Default bind: `0.0.0.0:8787` (`UXC_HOST` / `UXC_PORT`).

### Health honesty

```json
{
  "formats": ["application/ux-channel+json"],
  "codecs": ["json", "cxb"],
  "http": { "action": { "content_type": "application/ux-channel+json", ... } },
  "cap_required": ["Cart.add"],
  "policy": { "present_cap_must_verify": true }
}
```

- `formats` / `http` = what the HTTP endpoint actually serves today  
- `codecs` = what the peer library can encode/decode (CXB is library-ready; Accept negotiation not on `/action` yet)

### Cap policy

1. `Cart.add` always requires a valid cap → `unauthorized` / “capability token required” if missing  
2. Any Intent that includes `cap` must verify (open actions cannot carry a bogus cap and proceed)  
3. Morph HTML escapes free-form strings (no XSS via `sku`)  
4. Integer args (`qty`, `by`) reject non-integers (no silent coercion)

Wire/parse failures return a Result `{ ok:false, error, meta }` — never a bare non-IR body.

## Cap compatibility

Matches Python `CapabilityService` / `itsdangerous.URLSafeTimedSerializer`:

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

See `../python_forward/` — host mints (or asks peer to mint), POSTs `Cart.add`, returns `Result.ops` unchanged.

## Layout

```text
src/
  lib.rs
  types.rs
  wire_json.rs
  cap.rs
  cxb.rs
  op_tags.rs
  actions.rs
  peer.rs
  bin/uxc_check.rs
  bin/uxc_peer.rs
```

## Next

- [ ] HTTP Accept `+cxb` response path
- [ ] Byte-identical encode vs Python oracle freeform
- [ ] WASM island / mesh (later phases)
