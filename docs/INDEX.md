# ux-channel documentation index

**Start:** [../START_HERE.md](../START_HERE.md) (the only intro).
**Encyclopedia map (unchanged):** [../DOCS.md](../DOCS.md).
This file routes by **audience** and **Diátaxis mode**. It does not replace DOCS.md.

## Folder contract (Phase 2)

| Folder | Diátaxis mode | May contain | Must not contain |
|--------|---------------|-------------|------------------|
| `docs/guides/` | how-to | Goal-oriented recipes | Conceptual essays as primary form |
| `docs/reference/` | reference | Facts, signatures, tables | Learning narrative as primary form |
| `docs/internals/` | explanation | Why, architecture, C4 | Step lists as primary form |
| `docs/examples/` | examples | Worked recipes / pointers | Law |
| `docs/adr/` | ADR | Decisions (or an index of them) | Mixed how-to |

Specialized folders (`security/`, `ship/`, `design/`, `tutorial/`, `patterns/`, `archive/`) stay.
`docs/INDEX.md` is the map. Do not add a second competing map.

This layer owns Intent / Result / Cap / wire / peers / host runtime.
It does **not** own HTML trees or CSS.

Stale history: [archive/](archive/) — **do not cite as current law**.

---

## Audience

| You are… | Start (≤ 2 clicks from repo root) |
|----------|-----------------------------------|
| **New** | [../START_HERE.md](../START_HERE.md) |
| **Python app builder** | [../python/docs/start/GOLDEN_PATH.md](../python/docs/start/GOLDEN_PATH.md) · [../python/docs/start/HOW_TO.md](../python/docs/start/HOW_TO.md) |
| **Need the one idea** | [../MENTAL_MODEL.md](../MENTAL_MODEL.md) |
| **Need frozen names** | [../PUBLIC_API_FREEZE.md](../PUBLIC_API_FREEZE.md) |
| **Operator / CI** | [../OPERATIONAL.md](../OPERATIONAL.md) · [../TESTING.md](../TESTING.md) |
| **Rust / peer** | [../rust/README.md](../rust/README.md) · [../ARCHITECTURE.md](../ARCHITECTURE.md) |
| **Maintainer / agent** | [../AGENTS.md](../AGENTS.md) · [../CONTRIBUTING.md](../CONTRIBUTING.md) · [../AUTOMATION.md](../AUTOMATION.md) |

---

## By Diátaxis mode

### Tutorial

| Doc | Topic |
|-----|--------|
| [../START_HERE.md](../START_HERE.md) | First-time users (5-min morph) |
| [../python/docs/start/GOLDEN_PATH.md](../python/docs/start/GOLDEN_PATH.md) | Golden path app |
| [../python/docs/start/](../python/docs/start/) | Application encyclopedia (start here after START_HERE) |

### How-to

| Doc | Topic |
|-----|--------|
| [guides/first-app.md](guides/first-app.md) | Copy-paste FastAPI morph + checklist |
| [guides/application-loop.md](guides/application-loop.md) | Order of operations |
| [guides/regions-and-morph.md](guides/regions-and-morph.md) | Region uid, morph ops, control attrs |
| [guides/common-mistakes.md](guides/common-mistakes.md) | Ten failure modes |
| [examples/README.md](examples/README.md) | Example slot |
| [../python/docs/start/HOW_TO.md](../python/docs/start/HOW_TO.md) | How-to encyclopedia |
| [../python/docs/start/ERROR_HANDLING.md](../python/docs/start/ERROR_HANDLING.md) | Errors |
| [../python/docs/start/EXTENSIONS.md](../python/docs/start/EXTENSIONS.md) | Extend without bloat |
| [../OPERATIONAL.md](../OPERATIONAL.md) | Verify / CI / secrets |
| [../TESTING.md](../TESTING.md) | What green means |
| [../RECOVERY.md](../RECOVERY.md) | Hardening restore (GitHub-first) |
| [../python/CONTRIBUTING.md](../python/CONTRIBUTING.md) | Python host workflow |
| [../CONTRIBUTING.md](../CONTRIBUTING.md) | Root contributor contract |

### Reference

| Doc | Topic |
|-----|--------|
| [reference/vocabulary.md](reference/vocabulary.md) | Day-1 terms |
| [reference/client-runtime.md](reference/client-runtime.md) | Browser runtime doors |
| [reference/capabilities.md](reference/capabilities.md) | Caps / args_hash |
| [reference/state-planes.md](reference/state-planes.md) | session / client / db |
| [reference/import-rules.md](reference/import-rules.md) | Root vs package imports |
| [../REFERENCE.md](../REFERENCE.md) | HTTP / recipes |
| [../PUBLIC_API_FREEZE.md](../PUBLIC_API_FREEZE.md) | Frozen names |
| [../FAQ.md](../FAQ.md) | Common questions |
| [../TERMINOLOGY.md](../TERMINOLOGY.md) | Glossary |
| [../NAMING.md](../NAMING.md) | Intent ↔ name (Rust-parity caps) |
| [../SPEC/](../SPEC/) | Wire law |
| [../conformance/](../conformance/) | Golden vectors |
| [../python/STABILITY.md](../python/STABILITY.md) | Layout + identity law |
| [../python/ONTOLOGY.md](../python/ONTOLOGY.md) | Region / Bridge / Action |
| [../python/docs/](../python/docs/) | MkDocs encyclopedia (core, asgi, security, state, …) |
| [../CHANGELOG.md](../CHANGELOG.md) | History (not current teaching) |

### Explanation

| Doc | Topic |
|-----|--------|
| [internals/identity.md](internals/identity.md) | What this library is / is not |
| [internals/implementation-map.md](internals/implementation-map.md) | Where truth lives |
| [internals/c4.md](internals/c4.md) | C4-style context / containers |
| [adr/README.md](adr/README.md) | ADR index |
| [adr/001-design-choices.md](adr/001-design-choices.md) | Intent → Result decisions |
| [../MENTAL_MODEL.md](../MENTAL_MODEL.md) | Intent → Result |
| [../HOW_IT_WORKS.md](../HOW_IT_WORKS.md) | Flows & algorithms |
| [../ARCHITECTURE.md](../ARCHITECTURE.md) | System shape / monorepo rules |
| [../STRUCTURE.md](../STRUCTURE.md) | Monorepo map |
| [../LONGEVITY.md](../LONGEVITY.md) | Stable vs moving + anti-bloat doors |
| [../AUTOMATION.md](../AUTOMATION.md) | Ceremonial vs hand-coded |
| [../PACK_README.md](../PACK_README.md) | Pack notes |
| [../python/README.md](../python/README.md) | Python host |
| [../python/STRUCTURE.md](../python/STRUCTURE.md) | Python permanence |
| [../python/LAYOUT.md](../python/LAYOUT.md) | Layout |
| [S_TIER_SCORECARD.md](S_TIER_SCORECARD.md) | Scorecard |

---

## Layer 0 / 1 / 2 (existing pyramid)

Unchanged from [../DOCS.md](../DOCS.md):

- Layer 0: README (gate) + START_HERE (only intro)
- Layer 1: MENTAL_MODEL, PUBLIC_API_FREEZE, GOLDEN_PATH, SECURITY_AUDIT
- Layer 2: encyclopedia (`python/docs/`, SPEC, root essays)

---

## Sister layers

| Package | Role |
|---------|------|
| [ux-dom](https://github.com/bitplorer/ux-dom) | Render / Document |
| [ux-behavior](https://github.com/bitplorer/ux-behavior) | Product behavior → Ops |
| [ux-motion](https://github.com/bitplorer/ux-motion) | Presence / transition plans |
| [ux-compose](https://github.com/bitplorer/ux-compose) | Composition + product CLI |

Do not flatten these layers into this repo.
