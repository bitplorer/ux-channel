# Python host — long-term stability (how we avoid patchy work)

## Non-negotiables

1. **One map:** [`src/ux_channel/PACKAGE_MAP.json`](src/ux_channel/PACKAGE_MAP.json)  
   - Every implementation module lives in a cohesive package.  
   - Top-level names are **generated aliases only** (never hand-edited).

2. **One sync command:**
   ```bash
   python3 scripts/sync_python_layout.py          # regenerate
   python3 scripts/sync_python_layout.py --check  # CI / verify
   ```

3. **One public app entry:** `from ux_channel.day1 import …`  
   Root `from ux_channel import …` stays frozen for the same symbols.

4. **Rust names for shared law:** `CapService`, `mint`, `verify`, `hash_args`, `CapError`, `Intent`.  
   See repo [`NAMING.md`](../NAMING.md). No dual product speech.

5. **Host-only types keep host names:** `Channel`, `Region`, `RegionBook`.

## Test tiers (stable productivity)

| Tier | Command | Purpose |
|------|---------|---------|
| **Gate** | `make test-python` / `make verify` | Always green; no FastAPI; interop + day1 + layout |
| **Host** | `make test-python-host` | Regions, state, control, day1 surface (needs fastapi) |
| **Full** | optional full tree under `tests/` | Product extras when deps installed |

Do not grow the gate into the full suite. Do not skip the host suite when changing `host/` or `paint/`.

## How to change code without chaos

| Change | Do this |
|--------|---------|
| Add a module | Put it in the right package → add to PACKAGE_MAP → `sync_python_layout.py` |
| Rename a symbol | Shared with Rust? Follow Rust. Host-only? Update day1 + NAMING + tests in one commit |
| Fix a bug | Prefer fixing the **implementation package**, not a shim |
| New public API | Add to `day1` + root `__all__` + gate freeze test |

## What not to do

- Hand-edit `python/src/ux_channel/*.py` aliases  
- Reintroduce `CapabilityService` / `CapService.sign` duals  
- Import private helpers via partial shims (aliases re-export the full module)  
- Document three different “preferred imports” in three READMEs  

## Entry docs (only these)

| Doc | Role |
|-----|------|
| [README.md](README.md) | Start here |
| [STABILITY.md](STABILITY.md) | This file |
| [LAYOUT.md](LAYOUT.md) | Package map narrative |
| [ONTOLOGY.md](ONTOLOGY.md) | Region vs Bridge vs Action |
| [../NAMING.md](../NAMING.md) | Intent ↔ name (Rust parity) |
