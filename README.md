# ux-channel

A click is not a form post. It is a signed **Intent**.

```text
Any peer  ── Intent { action, args, cap } ──▶  Any peer
Any peer  ◀── Result { ok, ops[], error } ──  Any peer
```

The browser (or an agent, or a Rust process) says *do this action with these args*, and proves it with a **capability**. The host runs the action and answers with **ops** — morph this region, toast that, navigate there. One IR. Many surfaces.

JSON is the floor. CXB is the dense upgrade. Caps travel with the Intent. Classic IR 0.1 clients stay valid forever.

**IR:** `"v": "1"` · **Tree:** 2026-08-13 (architecture host/peer + classic floor)

---

**Start:** [START_HERE.md](START_HERE.md) · [MENTAL_MODEL.md](MENTAL_MODEL.md) · [DOCS.md](DOCS.md) · [AUTOMATION.md](AUTOMATION.md) · [python/STABILITY.md](python/STABILITY.md)

**Default:** automate ceremonial inventories (`make regen` / `make sync-map`); hand-code only features, law, and public API — see [AUTOMATION.md](AUTOMATION.md).

**Maps:** [ARCHITECTURE.md](ARCHITECTURE.md) · [DOCS.md](DOCS.md) · [NAMING.md](NAMING.md) · [python/LAYOUT.md](python/LAYOUT.md) · [python/ONTOLOGY.md](python/ONTOLOGY.md) — monorepo: `python/` + `rust/` + shared law.

**New here?** Read in order. Do not assume prior knowledge of IR / caps / CXB.

1. **[START_HERE.md](START_HERE.md)** — mental model, caps, first app, mistakes
2. **[TERMINOLOGY.md](TERMINOLOGY.md)** — what every word means, does, and is **not**
3. **[HOW_IT_WORKS.md](HOW_IT_WORKS.md)** — flows, algorithms, order of steps
4. **[REFERENCE.md](REFERENCE.md)** — HTTP API, curl recipes, module map
5. **[FAQ.md](FAQ.md)** — short answers

This tree is the living design + conformance + second-implementation surface: a Python host library, a Rust kernel/runtime, and the law both must obey.

---

## The four boxes

| | Kernel | Runtime |
|---|---|---|
| **Host** | Cap, nonce, registry, `project()` | `HostRuntime` / Python `Channel` |
| **Peer** | `PeerApply` — apply ops, **no DOM** | `PeerRuntime` — hello, submit, revoke |

Classic **`Peer`** (`uxc_peer`) is the demo Intent gate, not the kernel. `flow_id` is correlation, never authority. Cap key ≠ proof key.

---

## What this can actually do

Not another REST wrapper. A few things that are unusual, and real.

**A checkout button that cannot be replayed.**  
The host mints a **once** capability: this action, these args, this `jti`. Verify consumes the nonce *before* the handler. Store down? The pay path refuses. A stolen click is one shot.

**The same action for a human and an agent.**  
`Cart.add` is one handler. A browser sends a signed Intent; an agent sends the same IR. The peer kernel has **no DOM** — `web.v1` morphs HTML, `agent.v1` logs. You do not write two APIs.

**Ship a new UI without breaking last year's client.**  
The host builds an **EffectGraph** (`seq`, `invoke`, toast). `project(auto)` keeps the graph for a peer that advertised `seq`. A classic peer with no hello gets flattened toast/morph. IR 0.1 is a permanent floor.

**A Python app talking to a Rust peer (or the reverse).**  
Same Intent, same Cap HMAC, same Result ops. Golden vectors in `conformance/` are the law. If the two languages disagree, the vectors win — not whoever shipped last.

**A Result nobody forged.**  
Optional **effect proofs** (different key from Cap) bind `ok` + `ops` to a session generation. Peer verifies *before* any apply. `proofs=require` refuses peers that cannot check. Proof never authorizes the handler; Cap still does.

**HTML the server owns, DOM the kernel never touches.**  
You write the markup. Channel paints **regions**. Ops say “replace this slot.” The apply machine does not call `document.*` by string name. Drivers do.

**A multi-step wizard without a second permission system.**  
`meta.flow_id` is a tag so the host can resume. It is **not** a capability. Each money/delete step still mints its own Cap.

**Fail closed, on purpose.**  
Missing cap, bogus present cap, args hash mismatch, once replay, nonce store down, forged proof, over-budget ops — handler does not run, or apply does nothing. That is the product, not a missing feature.

These are the doors: [START_HERE.md](START_HERE.md) for the first app, [SPEC/architecture/](SPEC/architecture/) for the law.

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
| [SPEC/architecture/](SPEC/architecture/) | Host/peer kernel, project, proofs, flow (classic floor stays) |
| [conformance/](conformance/) | Golden JSON vectors + CXB expected blobs + `vectors/arch/` + harnesses |
| [PUBLIC_API_FREEZE.md](PUBLIC_API_FREEZE.md) | Application public names (host package alignment) |

### C. Product packages + demos

| Path | Role |
|------|------|
| **[python/](python/)** | **Full Python host package** (`ux_channel/`, wire, caps, ASGI, CXB oracle) |
| **[rust/](rust/)** | **Rust crate** — host+peer kernel/runtime, classic gate, cap, CXB |
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
| Architecture vectors (`vectors/arch/`) | **Green** |
| Python host interop (`python/tests`) | **Green** (same law as Rust) |
| HostRuntime + PeerApply (Python + Rust) | **Green** (classic floor preserved) |
| Optional trace + surface-hello | Present (additive) |
| Rust types + JSON round-trip | **Green** |
| Cap verify in Rust | **Green** (oracle + mint/verify) |
| once / jti consumption | **Enforced** (Python + Rust; health: `once_jti_enforced: true`) |
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
