# ux-channel — Wire-Native Peers (Intent → Action → Result / ops)

**Start:** [START_HERE.md](START_HERE.md) · [MENTAL_MODEL.md](MENTAL_MODEL.md) · [DOCS.md](DOCS.md) · [AUTOMATION.md](AUTOMATION.md) · [python/STABILITY.md](python/STABILITY.md)

**IR version:** `"v": "1"`  
**Date:** 2026-08-10 (clarity + consistency audit)

This folder is the living design + conformance + second-implementation surface for turning **ux-channel** from a strong Python library into a **wire-native peer platform**.

**Layout:** [ARCHITECTURE.md](ARCHITECTURE.md) · **Docs map:** [DOCS.md](DOCS.md) · **Naming:** [NAMING.md](NAMING.md) · **Python map:** [python/LAYOUT.md](python/LAYOUT.md) · [python/ONTOLOGY.md](python/ONTOLOGY.md) — monorepo with `python/` + `rust/` + shared law.

**New here?** (read in order)
1. **[START_HERE.md](START_HERE.md)** — full first-time path (mental model, caps, first app, mistakes)
2. **[TERMINOLOGY.md](TERMINOLOGY.md)** — what every word means, does, and is **not**
3. **[HOW_IT_WORKS.md](HOW_IT_WORKS.md)** — flows, algorithms, order of steps
4. **[REFERENCE.md](REFERENCE.md)** — HTTP API, curl recipes, module map
5. **[FAQ.md](FAQ.md)** — short answers
Do not assume prior knowledge of IR / caps / CXB.

---

## What this is

```text
Any peer  ── Intent { action, args, cap } ──▶  Any peer
Any peer  ◀── Result { ok, ops[], error } ──  Any peer
```

One IR, one trust story (capabilities), many surfaces (DOM, WASM, hardware, agents).  
JSON is the floor; CXB is the dense upgrade; caps travel with the Intent.

---

## Layout (structured)

Read top → bottom if you are new. Layers do not mix “law” with “demo.”

### A. Start here (humans)

| Path | Role |
|------|------|
| **[TERMINOLOGY.md](TERMINOLOGY.md)** | **Glossary** — every term: is / does / is-not / where |
| **[HOW_IT_WORKS.md](HOW_IT_WORKS.md)** | Full walkthrough: diagrams, algorithms, order of steps |
| **[REFERENCE.md](REFERENCE.md)** | HTTP API, curl, modules, how to add an action |
| **[FAQ.md](FAQ.md)** | Common confusions in short form |
| [ARCHITECTURE.md](ARCHITECTURE.md) | Production monorepo boundaries |
| [STRUCTURE.md](STRUCTURE.md) | Permanent (law) vs moving (demos) |
| [OPERATIONAL.md](OPERATIONAL.md) | Secrets, env vars, HTTP honesty — **before** `uxc_peer` |
| [AUTOMATION.md](AUTOMATION.md) | Ceremonial automation vs hand design |
| [AGENTS.md](AGENTS.md) | Short agent checklist |
| [CHANGELOG.md](CHANGELOG.md) | What landed in this tree |

### B. Law (change only via major IR or bugfix)

| Path | Role |
|------|------|
| [SPEC/](SPEC/) | IR, capability, invariants, breaking-change policy |
| [conformance/](conformance/) | Golden JSON vectors + CXB expected blobs + harnesses |
| [PUBLIC_API_FREEZE.md](PUBLIC_API_FREEZE.md) | Application public names (host package alignment) |

### C. Product packages + demos

| Path | Role |
|------|------|
| **[python/](python/)** | **Full Python host package** (`ux_channel/`, wire, caps, ASGI, CXB oracle) |
| **[rust/](rust/)** | **Rust peer crate** (types, wire, cap, CXB, HTTP bins) |
| [demos/python_forward/](demos/python_forward/) | Minimal Python → Rust forward (1 script, not the full library) |
| [conformance/harness/](conformance/harness/) | Stdlib Python vector validators |
| [startup-peer.sh](startup-peer.sh) | Idempotent local demo peer helper (oracle allow-listed) |

> **Looking for Python code?** Open [`python/README.md`](python/README.md) and [`python/src/ux_channel/`](python/src/ux_channel/).  
> `demos/python_forward` is only a tiny HTTP client — not the product library.

### D. Planning only (not law)

| Path | Role |
|------|------|
| [ux-channel-core-ideas.md](ux-channel-core-ideas.md) | Thesis / motivation |
| [ux-channel-design-causal-surface.md](ux-channel-design-causal-surface.md) | Optional envelopes (Phase 1.5) |
| [ux-channel-roadmap.md](ux-channel-roadmap.md) | Phased plan |

### E. One-command verify

```bash
./verify.sh                 # JSON + CXB harnesses + cargo test + uxc_check
./verify.sh --http          # also live peer smoke (starts demo peer if needed)
```

---

## Quick verification

Automation (prefer these — CI runs the same):

```bash
make verify        # repo health + law + rust
make verify-http   # + live peer smoke
```

Or directly:

```bash
./verify.sh
# or step by step:
python3 conformance/harness/validate_json_vectors.py
python3 conformance/harness/validate_cxb_expected.py

cd rust
cargo test --lib
cargo run --bin uxc_check -- ../conformance

# live peer (demo secret only — see OPERATIONAL.md)
UXC_ALLOW_ORACLE_SECRET=1 UXC_PORT=8787 cargo run --bin uxc_peer &
cargo run --bin uxc_check -- ../conformance --http http://127.0.0.1:8787

python3 demos/python_forward/forward_to_rust.py --base http://127.0.0.1:8787 --mint-via-peer
```

**Production peer:** set `UXC_CAP_SECRET` to a private value. Do **not** use the oracle secret. See [`OPERATIONAL.md`](OPERATIONAL.md).

---

## Current status (honest)

| Layer | State |
|-------|--------|
| SPEC + freeze + invariants + breaking policy | Drafted and consistent |
| Conformance JSON vectors + harness | **Green** |
| Python host interop (`python/tests`) | **Green** (same law as Rust) |
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
2. JSON floor — browsers & application always work  
3. Caps travel on the Intent  
4. Peers over FFI  
5. Optional envelopes never required for basic interop  
6. Breaking changes require a new major (`SPEC/BREAKING_CHANGE_POLICY.md`)  
7. Permanent core vs moving demos (`STRUCTURE.md`) — no long-term confusions  

---

**North star:** Don’t scale languages. Scale the Intent → Result → ops contract, and let every runtime be a peer.
