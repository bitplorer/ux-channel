# ux-channel — Wire-Native Peers (Intent → Action → Result / ops)

**Hand-off package for Grok Build**  
**IR version:** `"v": "1"`  
**Date:** 2026-08-10 (audit: stability, honesty, edge coverage)

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
| `SPEC/` | Normative drafts: Intent/Result/ops, Capability, Breaking-change policy |
| `conformance/` | Golden vectors + harnesses + **CXB expected blobs** |
| `peers/ux_channel_rs/` | Rust peer: types, JSON, cap, CXB, HTTP, `uxc_check` / `uxc_peer` |
| `peers/python_forward/` | Minimal Python → Rust forward (ops returned unchanged) |
| `PUBLIC_API_FREEZE.md` | Day-1 public surface aligned with package freeze docs |
| `ux-channel-core-ideas.md` | Platform thesis |
| `ux-channel-design-causal-surface.md` | Optional envelopes |
| `ux-channel-roadmap.md` | Phase map + current next steps |
| `AGENTS.md` | Agent orientation + intentional policies |
| `ux-channel-0.1.0.zip` | Original Python package (reference) |

---

## Quick verification

```bash
python3 conformance/harness/validate_json_vectors.py
python3 conformance/harness/validate_cxb_expected.py

cd peers/ux_channel_rs
cargo test --lib
cargo run --bin uxc_check -- ../../conformance
# optional live:
UXC_PORT=8787 cargo run --bin uxc_peer &
cargo run --bin uxc_check -- ../../conformance --http http://127.0.0.1:8787

python3 peers/python_forward/forward_to_rust.py --base http://127.0.0.1:8787 --mint-via-peer
```

---

## Current status (honest)

| Layer | State |
|-------|--------|
| SPEC + freeze + breaking policy | Drafted and consistent |
| Conformance JSON vectors + harness | **Green** |
| Optional trace + surface-hello | Present (additive) |
| Rust types + JSON round-trip | **Green** |
| Cap verify in Rust | **Green** (oracle + mint/verify) |
| HTTP action endpoint | **Green** (Result-shaped errors; honest health) |
| Python → Rust forward | **Green** |
| CXB expected blobs | **Green** (14 frozen) |
| Rust CXB encode/decode | **Green** (decode oracle; structural re-encode) |
| HTTP Accept `+cxb` | Not on wire yet (library codec only) |
| WASM / mesh | Not started |

### Intentional policies (not bugs)

- Missing `Cart.add` cap → `unauthorized` / “capability token required”
- Any present `cap` is verified (open actions cannot carry a bogus token)
- Health `formats` = what HTTP serves; `codecs` = library capability
- Integer args reject non-integers (no silent coercion)
- Morph HTML escapes free-form strings
- Wire/parse failures still return a Result IR body (`ok: false`)

---

## Principles (non-negotiable)

1. One IR — Intent / Result / ops; no parallel RPC style  
2. JSON floor — browsers & day-1 always work  
3. Caps travel on the Intent  
4. Peers over FFI  
5. Optional envelopes never required for basic interop  
6. Breaking changes require a new major (`SPEC/BREAKING_CHANGE_POLICY.md`)

---

**North star:** Don’t scale languages. Scale the Intent → Result → ops contract, and let every runtime be a peer.
