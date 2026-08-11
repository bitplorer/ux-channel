# Automation policy — ceremonial vs hand-coded

**Default: automate anything boring, repetitive, or easy to go stale.**  
Hand-code only design, trust boundaries, and domain behavior.

If a human is tempted to re-type a list that already exists on disk or in another file, that list is **automation territory**.

---

## North star

```text
Intent → Action → Result(ops)     # product law (hand design)
packages on disk                  # source of structure
  ↓  scripts/sync_python_layout.py
PACKAGE_MAP modules / catalog     # derived (never hand-edit)
  ↓  make verify / CI
fresh tree, no dead paths
```

---

## What is automated (default)

| Artifact | Generator | Hand-edit? |
|----------|-----------|------------|
| `PACKAGE_MAP.json` → `modules`, `module_count` | `scripts/sync_python_layout.py` | **Never** — derived from `packages` |
| `catalog/catalog.json` | same | **Never** |
| CXB expected blobs | `conformance/harness/regenerate_cxb_expected.py` | **Never** — from oracle |
| Bridge preset scaffolds | `bridge_preset_gen` / CLI | Prefer regen over patching output |
| TS client shell | `devtools.codegen.generate_ts_client` | Marked auto-generated |
| Repo health (links, stale names) | `scripts/repo_health.py` | N/A (check only) |
| Longevity strata import rules | `scripts/check_longevity.py` | N/A (check only) |

### Commands (prefer Make)

```bash
make regen          # layout + catalog derived fields
make layout         # CI check (fails if stale)
make sync-map       # opt-in: packages inventory from disk, then regen
make verify         # full green (health + layout + law + tests)
make cxb-regen      # rebuild CXB expected (needs PYTHONPATH)
```

Or directly:

```bash
python3 scripts/sync_python_layout.py              # write derived
python3 scripts/sync_python_layout.py --check      # fail if stale
python3 scripts/sync_python_layout.py --sync-map   # packages ← disk
```

**CI** (`.github/workflows/ci.yml` + `./verify.sh`) runs `--check`. Merging with a stale catalog is a hard fail.

---

## What stays hand-coded (opt-in human design)

| Surface | Why human |
|---------|-----------|
| `SPEC/`, invariants, cap/CXB tags | Wire law / trust |
| Package `__init__.py` export lists | Public API surface is product design |
| Action handlers, registry policy | Domain behavior |
| Cap crypto, wire codecs (logic) | Security / interop correctness |
| `packages` in PACKAGE_MAP (until `--sync-map`) | Intentional module placement |
| `strata`, `public_entry`, `package_docs` | Architecture labels |
| Application examples under `python/examples/` | Teaching intent |
| Rust peer logic | Second implementation of law |

Private helpers named `_*.py` are **not** auto-listed in the map (keep them private).

---

## Design / architecture / implementation overviews — where they live

| Question | Place |
|----------|--------|
| Why monorepo, law vs product | [ARCHITECTURE.md](ARCHITECTURE.md) |
| Permanent vs moving trees | [STRUCTURE.md](STRUCTURE.md) |
| Strata L1–L6, anti-bloat doors | [LONGEVITY.md](LONGEVITY.md) |
| Intent → Result mental model | [MENTAL_MODEL.md](MENTAL_MODEL.md) |
| Full flow algorithms | [HOW_IT_WORKS.md](HOW_IT_WORKS.md) |
| HTTP / curl / modules | [REFERENCE.md](REFERENCE.md) |
| Python layout + identity law | [python/STABILITY.md](python/STABILITY.md) |
| Package intent one-liners | `PACKAGE_MAP.json` → `package_docs` + each package `__init__.py` |
| Agent checklist | [AGENTS.md](AGENTS.md) |
| **This policy** | `AUTOMATION.md` (here) |

**Rule:** design overviews sit **next to the decision surface** they constrain — not a second parallel wiki. Package `__init__.py` docstring = “what this package is for + preferred import.” Deep impl notes stay in `python/docs/`.

---

## Keeping the tree fresh (nothing dead)

| Check | Fail condition |
|-------|----------------|
| `repo_health.py` | Missing required docs, broken md links, forbidden legacy package names, **session-only paths** (`/home/workdir`, agent artifact zips as “source of truth”) |
| `sync_python_layout.py --check` | Catalog or derived map fields out of date; unmapped `.py` modules |
| `check_longevity.py` | Strata drift, core eagerly imports L4 planes |
| `verify.sh` | Law vectors / CXB / gate tests / Rust |

After adding a module under `ux_channel/<pkg>/`:

1. Prefer `make sync-map` (or add the stem to `packages` once), then `make regen` is automatic in that path.  
2. Or add stem to `packages` and run `make regen`.  
3. Commit regenerated `PACKAGE_MAP.json` + `catalog/catalog.json` together.

Do **not** leave recovery docs pointing at dead agent sandbox paths — GitHub `main` + `patches/` are the durable source ([RECOVERY.md](RECOVERY.md), [HARDENING_STATUS.md](HARDENING_STATUS.md)).

---

## Implementation sketch (layout sync)

```text
disk  ux_channel/<pkg>/*.py
        │
        │  --sync-map (opt-in)
        ▼
PACKAGE_MAP.packages          ← intentional inventory
        │
        │  always
        ▼
modules + module_count        ← pure function of packages
catalog/catalog.json          ← pure function of packages + public_entry
        │
        ▼
--check compares expected vs on-disk files (no write)
```

---

## Anti-patterns

1. Hand-editing `catalog.json` or `modules` “just this once.”  
2. Copy-pasting module lists into three docs.  
3. Leaving `__init__.py` re-export tables that disagree with reality without a gate test.  
4. Treating zip/agent workspace paths as the long-term source of truth.  
5. Asking humans to re-run ceremonial steps that `make verify` already covers.
