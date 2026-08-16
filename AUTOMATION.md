# Automation policy — default automate, hand-code only when it matters

## Default (opt-in to *hand* work, not to automation)

**Automation is the default** for anything ceremonial, repetitive, inventory-like,
or easy to go stale. You **opt into hand-coding** only when:

1. **Extending features** — new domain behavior, new public API, new trust rules  
2. **Breaking / law changes** — IR major, cap tags, freeze surface, invariants  
3. **Security / interop logic** — crypto, codecs, peer gate correctness  

If a human is tempted to re-type a list that already exists on disk or in another
file, that list is **automation territory**. Prefer `make regen` / `make sync-map`
over editing derived JSON by hand.

```text
                     ┌─────────────────────────────┐
   Hand design ─────►│ SPEC · handlers · __all__   │  opt-in human work
                     │ trust boundaries · IR law   │
                     └──────────────┬──────────────┘
                                    │
                     ┌──────────────▼──────────────┐
   Automation ──────►│ modules · catalog · CXB     │  DEFAULT — never hand-stale
   (ceremonial)      │ expected · layout checks    │
                     └──────────────┬──────────────┘
                                    │
                     ┌──────────────▼──────────────┐
   Gates ───────────►│ make verify / CI            │  fails closed on drift
                     └─────────────────────────────┘
```

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

## What is automated (default — do not hand-edit)

| Artifact | Generator | Hand-edit? |
|----------|-----------|------------|
| `PACKAGE_MAP.json` → `modules`, `module_count` | `scripts/sync_python_layout.py` | **Never** — derived from `packages` |
| `catalog/catalog.json` (+ `package_docs`, `strata`) | same | **Never** |
| Catalog `__init__.py` helpers | same | Prefer regen |
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

**CI** (`.github/workflows/ci.yml` + `./verify.sh`) runs `--check`. Merging with a
stale catalog is a hard fail.

---

## What stays hand-coded (opt-in human design)

| Surface | Why human | When to touch |
|---------|-----------|---------------|
| `SPEC/`, invariants, cap/CXB tags | Wire law / trust | Bugfix or **breaking** IR major |
| Package `__init__.py` export lists | Public API is product design | **Extending** the public surface |
| Package `__init__.py` design overview | Architecture next to the package | When the package's role changes |
| Action handlers, registry policy | Domain behavior | **Feature** work |
| Cap crypto, wire codecs (logic) | Security / interop correctness | Bugfix or law change |
| `packages` in PACKAGE_MAP (until `--sync-map`) | Intentional module placement | New modules (or `make sync-map`) |
| `strata`, `public_entry`, `package_docs` | Architecture labels | Renames / new packages |
| Application examples under `python/examples/` | Teaching intent | Demos |
| Rust crate logic | Second implementation of law | Kernel/runtime features / bugfixes |

Private helpers named `_*.py` are **not** auto-listed in the map (keep them private).

**Rule of thumb:** if the change is “make a list match disk again,” automate it.
If the change is “apps should call a new name or trust a new rule,” hand-code it.

---

## Design / architecture / implementation overviews — where they live

Place overviews **next to the decision surface** they constrain — not a second wiki.

| Question | Place |
|----------|--------|
| Why monorepo, law vs product | [ARCHITECTURE.md](ARCHITECTURE.md) |
| Permanent vs moving trees | [STRUCTURE.md](STRUCTURE.md) |
| Strata L1–L6, anti-bloat doors | [LONGEVITY.md](LONGEVITY.md) |
| Intent → Result mental model | [MENTAL_MODEL.md](MENTAL_MODEL.md) |
| Full flow algorithms | [HOW_IT_WORKS.md](HOW_IT_WORKS.md) |
| HTTP / curl / modules | [REFERENCE.md](REFERENCE.md) |
| Python layout + identity law | [python/STABILITY.md](python/STABILITY.md) |
| Package intent one-liners | `PACKAGE_MAP.json` → `package_docs` (+ mirrored in generated `catalog.json`) |
| Package design/arch/impl | each package `__init__.py` docstring (short Design / Architecture / Implementation) |
| Deep API encyclopedia | `python/docs/` |
| Agent checklist | [AGENTS.md](AGENTS.md) |
| **This policy** | `AUTOMATION.md` (here) |

**Package docstring contract (hand-maintained, short):**

```text
"""One-line role.

Design: why this package exists / what it owns.
Architecture: how it sits in L0–L6 and peers.
Implementation: where the real code lives; preferred imports.

    from ux_channel.<pkg> import …
"""
```

Do not duplicate full HOW_IT_WORKS into every package. Link up to root docs when deep.

---

## Keeping the tree fresh (nothing dead)

| Check | Fail condition |
|-------|----------------|
| `repo_health.py` | Missing required docs, broken md links, forbidden legacy package names, **session-only paths** (`/home/workdir`, agent artifact zips as “source of truth”) |
| `sync_python_layout.py --check` | Catalog or derived map fields out of date; unmapped `.py` modules |
| `check_longevity.py` | Strata drift, core eagerly imports L4 planes |
| `verify.sh` | Law vectors / CXB / gate tests / Rust |

After adding a module under `ux_channel/<pkg>/`:

1. Prefer `make sync-map` (packages inventory from disk + regen).  
2. Or add stem to `packages` and run `make regen`.  
3. Commit regenerated `PACKAGE_MAP.json` + `catalog/catalog.json` together.  
4. If the package's role changed, update `__init__.py` Design/Architecture lines and `package_docs`.

Do **not** leave recovery docs pointing at dead agent sandbox paths — GitHub `main`
+ `patches/` are the durable source ([RECOVERY.md](RECOVERY.md),
[docs/archive/HARDENING_STATUS.md](docs/archive/HARDENING_STATUS.md)).

Historical merge notes must not reintroduce forbidden names (`zones`, `day1`,
`paint`, shims) as if they still ship — see [python/MERGE.md](python/MERGE.md).

---

## Implementation sketch (layout sync)

```text
disk  ux_channel/<pkg>/*.py
        │
        │  --sync-map (opt-in inventory)
        ▼
PACKAGE_MAP.packages          ← intentional inventory (or disk)
        │
        │  always (ceremonial)
        ▼
modules + module_count        ← pure function of packages
catalog/catalog.json          ← packages + public_entry + package_docs + strata
        │
        ▼
--check compares expected vs on-disk files (no write)
```

Import-identity smoke (Channel ≡ api ≡ host, CapService single identity) runs when
host deps are available; layout/catalog freshness still fails closed without them.

---

## Anti-patterns

1. Hand-editing `catalog.json` or `modules` “just this once.”  
2. Copy-pasting module lists into three docs.  
3. Leaving `__init__.py` re-export tables that disagree with reality without a gate test.  
4. Treating zip/agent workspace paths as the long-term source of truth.  
5. Asking humans to re-run ceremonial steps that `make verify` already covers.  
6. Hand-coding a new inventory after every file add instead of `make sync-map`.  
7. Writing a second architecture wiki instead of a short overview on the package that owns the decision.
