# Best of both worlds — merge notes

## Sources

| Source | What we kept |
|--------|----------------|
| **Attached / release 0.1.0** | `src/` layout, full `docs/`, full `tests/` tree, `examples/`, package `scripts/`, `ux_channel_ux_dom`, domain docs |
| **Monorepo evolution** | `zones/`, `day1`, sorted `args_hash`, gate tests, Rust interop, `LAYOUT`/`ONTOLOGY`/`STRUCTURE`, verify/CI |

## Not lost

- All `ux_channel` modules from release (**plus** `day1` + `zones`)
- Cap algorithm **fixed** to sorted compact JSON (Rust/oracle compatible) — do not revert to unsorted serde dumps
- Full documentation encyclopedia under `docs/`
- Full optional test suites under `tests/{core,regions,…}`
- Examples with `PYTHONPATH=python/src`

## Always green (CI)

Only `tests/gate/` runs in `make verify` (no FastAPI required).

Full suite is optional when extras are installed.

## Cohesive packages (later refinement)

Implementations moved into domain packages; top-level names remain as shims. See LAYOUT.md.
