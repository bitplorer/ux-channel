# ux-channel — Wire-Native Peers (Intent → Action → Result / ops)

**IR version:** `"v": "1"`  
**Date:** 2026-08-10 (clarity + consistency audit)

This folder is the living design + conformance + second-implementation surface for turning **ux-channel** from a strong Python library into a **wire-native peer platform**.

---

## What this is

```text
Any peer  ── Intent { action, args, cap } ──▶  Any peer
Any peer  ◀── Result { ok, ops[], error } ──  Any peer
```

One IR, one trust story (capabilities), many surfaces (DOM, WASM, hardware, agents).  
JSON is the floor; CXB is the dense upgrade; caps travel with the Intent.

---

## Layout

| Path | Role |
|------|------|
| `SPEC/` | Normative drafts: IR, Capability, Invariants, Breaking-change policy |
| `STRUCTURE.md` | Permanent vs moving (do not mix law with demos) |
| `OPERATIONAL.md` | Secrets, env vars, HTTP honesty — **read before running `uxc_peer`** |
| `conformance/` | Golden vectors + harnesses + **CXB expected blobs** |
| `peers/ux_channel_rs/` | Rust peer: types, JSON, cap, CXB, HTTP, `uxc_check` / `uxc_peer` |
| `peers/python_forward/` | Minimal Python → Rust forward (ops returned unchanged) |
| `PUBLIC_API_FREEZE.md` | Day-1 public surface aligned with package freeze docs |
| `AGENTS.md` | Agent orientation + intentional policies |
| `ux-channel-*.md` | Thesis / causal surface / roadmap (planning, not law) |

---

## Quick verification

```bash
python3 conformance/harness/validate_json_vectors.py
python3 conformance/harness/validate_cxb_expected.py

cd peers/ux_channel_rs
cargo test --lib
cargo run --bin uxc_check -- ../../conformance

# live peer (demo secret only — see OPERATIONAL.md)
UXC_ALLOW_ORACLE_SECRET=1 UXC_PORT=8787 cargo run --bin uxc_peer &
cargo run --bin uxc_check -- ../../conformance --http http://127.0.0.1:8787

python3 peers/python_forward/forward_to_rust.py --base http://127.0.0.1:8787 --mint-via-peer
```

**Production peer:** set `UXC_CAP_SECRET` to a private value. Do **not** use the oracle secret. See [`OPERATIONAL.md`](OPERATIONAL.md).

---

## Current status (honest)

| Layer | State |
|-------|--------|
| SPEC + freeze + invariants + breaking policy | Drafted and consistent |
| Conformance JSON vectors + harness | **Green** |
| Optional trace + surface-hello | Present (additive) |
| Rust types + JSON round-trip | **Green** |
| Cap verify in Rust | **Green** (oracle + mint/verify) |
| once / jti consumption | **Gap** (SPEC requires; Rust Cap 0.1 not yet; health: `once_jti_enforced: false`) |
| HTTP action endpoint | **Green** (Result-shaped errors; honest health; no silent oracle; 401 on `unauthorized`) |
| Python → Rust forward | **Green** |
| CXB expected blobs | **Green** (14 frozen) |
| Rust CXB encode/decode | **Green** (decode oracle; structural re-encode) |
| HTTP Accept `+cxb` | Not on wire yet (library codec only) |
| WASM / mesh | Not started |

### Intentional policies (not bugs)

| Policy | Behavior |
|--------|----------|
| Cap required | Missing `Cart.add` cap → `unauthorized` / “capability token required” |
| Present-cap-must-verify | Any present `cap` is verified (health: `present_cap_must_verify`) |
| Health honesty | `formats` = what HTTP serves; `codecs` = library capability; `demo_mode` + `once_jti_enforced` advertised |
| Integer args | Reject non-integers (no silent coercion) |
| Escape | Morph HTML **and** toast display text escape free-form strings; `signal_set` stays raw |
| Result-shaped wire | Wire/parse failures still return a Result IR body (`ok: false`) |
| Fail-closed secrets | `uxc_peer` refuses a silent public oracle secret unless `UXC_ALLOW_ORACLE_SECRET=1` |
| HTTP status | Secondary to Result: 200 / 401 (`unauthorized`) / 400 / 500 |

---

## Principles (non-negotiable)

1. One IR — Intent / Result / ops; no parallel RPC style  
2. JSON floor — browsers & day-1 always work  
3. Caps travel on the Intent  
4. Peers over FFI  
5. Optional envelopes never required for basic interop  
6. Breaking changes require a new major (`SPEC/BREAKING_CHANGE_POLICY.md`)  
7. Permanent core vs moving demos (`STRUCTURE.md`) — no long-term confusions  

---

**North star:** Don’t scale languages. Scale the Intent → Result → ops contract, and let every runtime be a peer.
