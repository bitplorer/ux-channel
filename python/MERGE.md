# Merge notes (historical — not current layout law)

**Current truth:** [STABILITY.md](STABILITY.md) · [../AUTOMATION.md](../AUTOMATION.md) · [../STRUCTURE.md](../STRUCTURE.md).  
This file only explains *what was combined*; it is not a live inventory.

## Sources (what landed in the monorepo)

| Source | What we kept |
|--------|----------------|
| **Release 0.1.0 host** | `src/` layout, full `docs/`, full `tests/` tree, `examples/`, package `scripts/`, `ux_channel_ux_dom` |
| **Monorepo evolution** | `catalog/` (generated), `api`, sorted `args_hash`, gate tests, Rust interop, verify/CI |

## Not lost

- Host modules under cohesive packages (`protocol`, `host`, `render`, …) plus curated `api`
- Cap algorithm **fixed** to sorted compact JSON (Rust/oracle compatible) — do not revert
- Full documentation encyclopedia under `docs/`
- Full optional test suites under `tests/{core,regions,…}`
- Examples with `PYTHONPATH=python/src`

## Forbidden — do not reintroduce

| Old name | Status |
|----------|--------|
| `zones` | **Removed** — use generated `catalog` |
| `day1`, `paint`, `ops_dx`, `bridge_meta` | **Removed** — see STABILITY rename table |
| Top-level shims / dual module paths | **Forbidden** — packages by intent only |

## Always green (CI)

`make verify` runs health, layout freshness, longevity, law vectors, `tests/gate/`, and Rust.  
Full host suite is optional when extras are installed (`make test-python`).

## Automation (current)

Module inventories and `catalog/catalog.json` are **derived** — never hand-edited.
See [../AUTOMATION.md](../AUTOMATION.md).
