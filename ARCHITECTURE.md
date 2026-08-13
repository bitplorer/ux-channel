# Architecture — production layout for the long run

**Longevity strata + anti-bloat doors:** [LONGEVITY.md](LONGEVITY.md).  
**Ceremonial automation (catalog, map, CXB expected):** [AUTOMATION.md](AUTOMATION.md).

**Decision:** keep **Python + Rust in one monorepo**, with **hard package boundaries** and a **shared law layer**.  
Do **not** split into multiple repos until release volume forces it — protocol drift is worse than a larger tree.

---

## Why monorepo (stability)

| Concern | Multi-repo risk | Monorepo mitigation |
|---------|-----------------|---------------------|
| IR / cap / CXB drift | Spec updates land in one language first | `SPEC/` + `conformance/` are shared law; both impls must pass `./verify.sh` |
| Golden vectors | Copy-paste rot | One `conformance/` tree |
| Cap oracle / args_hash | Silent interop breaks | Same vectors + `uxc_check` + Python harnesses |
| Onboarding | “Where is truth?” | One README → ARCHITECTURE → TERMINOLOGY |

**Independent product releases still exist:**

| Artifact | Path | Release channel (target) |
|----------|------|---------------------------|
| Python host library | `python/` | PyPI (`ux-channel`) |
| Rust crate | `rust/` | crates.io (`ux_channel_rs`) |
| Law + vectors | `SPEC/` + `conformance/` | Versioned with IR major (`v: "1"`) |

Crate/package versions may differ; **IR major must match**.

---

## Layout (production)

```text
repo root
├── SPEC/                 LAW — normative drafts (IR, cap, invariants)
├── conformance/          LAW — golden JSON + CXB blobs + harnesses
├── python/               PRODUCT — full host library (ASGI, wire, caps, …)
│   └── ux_channel/
├── rust/                 PRODUCT — host+peer kernel/runtime + classic gate + CXB
│   └── src/ + bins uxc_peer, uxc_check
├── demos/                MOVING — examples only, not production deps
│   └── python_forward/   thin Intent POST to Rust peer
├── docs guides           HOW_IT_WORKS, TERMINOLOGY, REFERENCE, FAQ, …
├── AUTOMATION.md         what is generated vs hand design
├── verify.sh             one-command green for both products + law
└── startup-peer.sh       local demo helper (oracle allow-listed)
```

```mermaid
flowchart TB
  subgraph LAW["LAW — change via IR major or bugfix"]
    SPEC[SPEC/]
    CONF[conformance/]
  end
  subgraph PROD["PRODUCT packages — ship independently"]
    PY[python/ux_channel]
    RS[rust/ ux_channel_rs]
  end
  subgraph DEMO["DEMOS — replace freely"]
    PF[demos/python_forward]
    UI[uxc_peer demo HTML]
  end
  subgraph AUTO["AUTOMATION — derived, never hand-stale"]
    MAP[PACKAGE_MAP modules/count]
    CAT[catalog.json]
    CXB[expected/cxb]
  end
  SPEC --> PY
  SPEC --> RS
  CONF --> PY
  CONF --> RS
  PY --> PF
  RS --> PF
  RS --> UI
  PY --> MAP
  PY --> CAT
  CONF --> CXB
```

---

## Design / implementation placement

| Layer | What you design by hand | What automation owns |
|-------|-------------------------|----------------------|
| Law | SPEC text, golden JSON vectors | CXB expected blobs from oracle |
| Python core | Action handlers, cap logic, package `__init__` exports | `modules` / `module_count` / catalog |
| Rust crate | Host/peer kernel+runtime, cap, CXB, HTTP bins | (n/a — rustc is the check) |
| Tooling L5 | CLI UX, dashboard copy | Preset/codegen outputs |

Package one-liners: `python/src/ux_channel/PACKAGE_MAP.json` → `package_docs`.  
Deeper API encyclopedia: `python/docs/`.

---

## Rules that keep this mature

1. **Law first.** If Python and Rust disagree, vectors win; fix the bug or cut a major.  
2. **No business logic in demos.** `demos/python_forward` must not grow into a second host.  
3. **Peer gate is permanent; actions/HTTP chrome are moving** (see STRUCTURE.md).  
4. **Secrets fail closed** in any production binary (OPERATIONAL.md).  
5. **JSON floor forever for IR 0.1**; CXB is opt-in upgrade.  
6. **CI gate:** `./verify.sh` before merge (includes **Python + Rust** + law); `--http` before release candidates.  
   Python suite: `python/tests` (cap oracle, JSON vectors, CXB expected). Rust: `cargo test` + `uxc_check`.  
7. **Do not nest a production crate under `peers/`** — that name signals “optional experiment.” First-class `rust/` + `python/` signal ship-ready packages.  
8. **Derived artifacts stay fresh** — `make layout` fails if catalog or map fields lag disk/packages ([AUTOMATION.md](AUTOMATION.md)).

---

## When to split repos later

Split **only if** all of the following hold:

- Separate teams own Python vs Rust release trains  
- Cross-repo IR drift is controlled by a published conformance package  
- CI can still block merge on foreign-language vectors  

Until then, monorepo + clear roots is the lower-risk production default.

---

## Commands

Prefer Make (CI uses the same):

```bash
make regen          # derived catalog + map fields
make verify         # health + layout + longevity + law + tests
make verify-http    # + live peer
make sync-map       # opt-in packages inventory from disk
```
