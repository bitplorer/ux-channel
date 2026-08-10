## 2026-08-10 — LONGEVITY: stable strata + anti-bloat extension doors

- Document L0–L6 permanence model (law → demos)
- Extension doors: hooks, stores, wire plugins, bridge plugins, caller planes, adapters, extras
- Wire DOCS/ARCHITECTURE/STABILITY + repo_health required file

---

## 2026-08-10 — deeper: root binds application only (power off root)

- Root no longer re-exports stores, ssr_state, planes, ChannelTest, sel, …
- Import power from packages (host.stores, host.testing, host.state_planes, …)
- Tests/examples migrated; gate freezes MemoryStateStore off root

---

## 2026-08-10 — deeper: root __all__ application tier

- Root __all__ ~50 application/stable symbols (was 88)
- Power re-exports still bound (e.g. MemoryStateStore) but not star-imported
- api package aligned; freeze + STABILITY document tiers

---

## 2026-08-10 — cleanup noise: drop PACKAGE/MEMBERS, thin STRUCTURE

- Remove PACKAGE/MEMBERS layout leftovers from all package __init__
- Real exports on io_adapters, asgi, realtime, transport, static
- python/STRUCTURE.md pointer-only; DOCS background essay section
- Gate freezes no PACKAGE/MEMBERS noise

---

## 2026-08-10 — remove MANUAL_PUBLIC_API magic comment

- Not a shell var or Python export — was only a layout-script guard string
- All package __init__.py are hand-maintained; sync only regenerates catalog
- Layout check fails if the stale marker reappears

---

## 2026-08-10 — deeper+wider: PACKAGE_MAP v3 (package.stem keys)

- Module map keys are package.stem — allows policy/errors/plugins in multiple packages
- Layout check: unmapped on-disk modules fail; multi-package import smoke
- Auto-init generation only for cohesive packages; MANUAL_PUBLIC_API on product pkgs
- Catalog lists full ux_channel.pkg.mod paths for every package

---

## 2026-08-10 — deep cleanup: action_catalog, tool_audit, mint_cap naming

- host/catalog.py → host/action_catalog.py (≠ catalog/ navigator)
- agent_runtime/audit.py → tool_audit.py (≠ devtools.audit)
- Remove CapService._hash_args; use hash_args only
- ChannelTest(sign=) → mint_cap=; AgentPeer/AgentRunner sign_caps → mint_caps
- Docs disambiguation tables; python README → docs/index

---

## 2026-08-10 — deeper cleanup: agent peer into agent_runtime kernel

- Move devtools/agent_peer.py → agent_runtime/peer.py (caller-plane cohesion)
- PACKAGE_MAP: product package agents→agent_runtime; modules include peer
- Gate: agent_runtime kernel surface; no callable package; agents() façade separate

---

## 2026-08-10 — caller planes analysis; pure agent_runtime kernel

- Document caller planes (human / agent_runtime / mcp / guest / workplace / peer)
- agent_runtime: pure implementation (AgentRunner…); remove callable-module hack
- Keep name agent_runtime; no umbrella runtimes/ until a new principal class needs it

---

## 2026-08-10 — deeper×2 + wider: freeze truth, agent_runtime, identity matrix

- PUBLIC_API_FREEZE rewritten (mint, stores, current packages)
- python/STRUCTURE.md de-staled; README + rust parity table
- Rename package `agents/` → `agent_runtime/` (stops shadowing `agents()` façade)
- Layout check: full identity matrix + wire/asgi smoke
- Gate: freeze doc + product package imports

---

## 2026-08-10 — cleanup deeper+wider: mental model + stability truth

- Rewrite python/STABILITY.md (correct rename table, identity, stores)
- Add MENTAL_MODEL.md; wire DOCS + ONTOLOGY + repo_health
- Rename remaining test_*dx* → test_*devtools*
- NAMING + LAYOUT pointers; health ignores rename-doc false positives

---

## 2026-08-10 — deeper+wider pass 2: verify layout, public API constants, tests

- verify.sh runs sync_python_layout --check (fixed quoting)
- DAY1_*_API → CHANNEL/WEBRTC/MEDIA_PUBLIC_API everywhere
- tests/dx → tests/devtools; path-stable webrtc example/static tests
- STRUCTURE.md monorepo map; gate rust-parity + public API constant freezes
- remove stale check_python_layout.py

---

## 2026-08-10 — deeper + wider monorepo consistency

- Active tree jargon sweep (demo→render.kit, CapService.sign→mint, …)
- Product surfaces: `wire` (core+cxb), `asgi.mount_channel`
- repo_health: forbidden layout dirs + required files + stale path scan
- Makefile: layout, test-python-gate, test-python-host
- Docs map + broken link neutralization; gate wire/asgi/api identity tests

---

## 2026-08-10 — deeper: stores module, api via packages, identity law

- `host/state.py` → `host/stores.py` (no collision with `state()` API)
- `api` package re-exports through host/protocol/devtools surfaces
- Module banner docs: Day-1/DX → Application/Developer tooling
- Channel.describe paths: render.kit; public_api_names docstring accurate
- STABILITY identity law + stores table; gate stores test

---

## 2026-08-10 — package surface polish (root via packages)

- Root re-exports primarily through package public APIs
- Richer protocol/render/security/devtools/bridge surfaces
- Document host.state vs state() name collision; gate identity tests

---

## 2026-08-10 — deep clean: map v2, package surfaces, harness paths

- Rebuild PACKAGE_MAP.json from disk (v2) with forbidden_names
- MANUAL_PUBLIC_API on host/protocol/render/security/foundations/…
- Root package docstring: professional import map only
- CXB harness finds monorepo `python/src` without PYTHONPATH
- Gate: cohesive package export smoke

---

## 2026-08-10 — thorough cleanup wave (professional names)

- `paint` → `render` (`renderers`, `kit`)
- `zones` → `catalog`
- `recipes` → `patterns`, `planes` → `state_planes`, `jsonutil` → `json_codec`
- `Channel.mental_model` → `Channel.describe`
- `examples/dx_dashboard` → `examples/dashboard`
- String import paths fixed after shim removal (`ux_channel.realtime.*`)
- Layout check forbids legacy package dirs

---

## 2026-08-10 — professional package names (no DX/meta jargon)

- `host/dx.py` → `host/channel.py`
- `devtools/` → `devtools/` (`dx_*` modules → dashboard/log/errors)
- `bridge/` → `bridge/`

---

## 2026-08-10 — rename day1 → api (professional public surface)

- Package `ux_channel.api` replaces informal `day1`
- `CHANNEL_PUBLIC_API` / `Channel.public_api_names()` replace day1_* naming
- Root `from ux_channel import …` remains the primary professional import

---

## 2026-08-10 — package public APIs + docs map + mint consistency

- `protocol` / `host` / `paint` expose primary symbols on the package
- Root [DOCS.md](DOCS.md) documentation index
- Remaining `sign`→`mint` and serde import drift cleaned
- sync preserves MANUAL_PUBLIC_API package inits

---

## 2026-08-10 — single-truth Python: packages only, zero shims

- Removed all top-level compatibility aliases
- Implementations only under cohesive packages; public via root + day1/
- security_plane → security; day1 is a real package
- sync_python_layout validates no top-level modules

---

## 2026-08-10 — durable Python host layout (no patchy drift)

- `PACKAGE_MAP.json` single source of truth for module→package
- `scripts/sync_python_layout.py` generates aliases + catalog; `--check` in CI
- `python/STABILITY.md` long-term rules; slim README; fewer doc entry points
- Gate contract test; host suite 203 passed

---

## 2026-08-10 — Python host stability: shims + day-1 mint + host suite

### Fixed
- Top-level import shims are full module aliases (private names like `_id_str` work)
- Day-1 Channel API lists **`mint`** (not `sign`) for caps
- Components/agent_peer use `registry.mint` detection
- Host regression suite: regions, state, day1, control — 201 passed
- `make test-python-host` target

---

## 2026-08-10 — Rust-parity names for shared cap API

### Breaking (0.1 alignment with Rust)
- `CapabilityService` → **`CapService`**
- `CapabilityError` → **`CapError`**
- Cap create method **`mint` only** (removed dual `sign` on CapService)
- `Channel.mint` / `ActionRegistry.mint` (was `.sign` for caps)
- `CapService.hash_args` public (Rust `hash_args`)
- Removed `RegionRegistry` alias (host-only `RegionBook` remains)

Ticket helpers (`sign_push`, `sign_ws`, …) unchanged — not the cap API.

---

## 2026-08-10 — cohesive packages (mature library structure)

### Structure
- Physical packages: `protocol`, `host`, `paint`, `security`, `transport`, `foundations`, `realtime`, `bridge`, `devtools`
- Top-level modules are **thin compatibility shims** (0.x imports unchanged)
- Coupling rules documented in `python/LAYOUT.md`
- No features removed; gate 31 + Rust green

---

## 2026-08-10 — best of both: release layout + monorepo enhancements

### Merged from release zip
- `python/src/ux_channel` (classic src layout)
- full `docs/`, `tests/`, `examples/`, `scripts/`, `ux_channel_ux_dom`

### Kept from monorepo evolution
- zones, day1, sorted args_hash, gate tests, Rust verify/cross-mint

---

## 2026-08-10 — Python zones (anti-flat layout)

### Added
- `ux_channel.catalog.*` — intent hubs (protocol, host, render, …)
- `python/LAYOUT.md` — every top-level module mapped to a zone
- `scripts/check_python_layout.py` — fail if orphans appear
- FAQ: flat tree vs stale/drift clarified

Implementations keep stable import paths (no mass rename breakage).

---

## 2026-08-10 — Python host long-term stability structure

### Added
- `ux_channel.api` — narrow frozen import façade for apps
- `python/STRUCTURE.md` — permanent vs moving inside the host package
- Day-1 tests: regions (morph uid, refresh), public API freeze, cap/wire smoke
- Gate now covers host UX plane, not only IR interop

---

## 2026-08-10 — Python ontology map (regions & friends)

### Added
- `python/ONTOLOGY.md` — logical/ontological map so users pick Region vs Bridge vs Action vs state correctly
- `python/docs/regions/*` and `python/docs/start/*` (layers, golden path, API surface)
- TERMINOLOGY + FAQ entries for Region / RegionBook

---

## 2026-08-10 — close remaining monorepo gaps

### Fixed / added
- Root `LICENSE` (MIT)
- `requirements-dev.txt` for gate deps; CI/verify install from it
- Relax `python/pyproject.toml` to Python >=3.10 (was 3.14-only)
- `repo_health` enforces verify.sh runs **both** Python pytest and Rust cargo
- Docs: AGENTS/STRUCTURE wording for dual-language gate

---

# Changelog — ux-channel wire-native package

History of **this** repository tree (`bitplorer/ux-channel`), not the full PyPI host package.

Format: newest first. “Law” vs “demo” follows [STRUCTURE.md](STRUCTURE.md).

---

## 2026-08-10 — Python + Rust both required in verify gate

### Fixed
- `CapService._hash_args` now uses **sorted compact JSON** (SPEC/oracle/Rust) — was unsorted serde dumps (interop break)

### Added
- `python/tests/test_interop_conformance.py` — cap oracle, JSON vectors, CXB expected
- `./verify.sh` / CI / `make test-python` run Python suite every time

---

## 2026-08-10 — automation so humans do not re-audit by hand

### Added
- `.github/workflows/ci.yml` — runs repo health + `./verify.sh` (+ `--http`)
- `scripts/repo_health.py` — broken links, stale paths, required files
- `Makefile` — `make verify`, `make verify-http`, `make peer-demo`, …
- `verify.sh` now runs repo health first

---

## 2026-08-10 — production monorepo layout

### Changed
- **Architecture decision:** keep Python + Rust together; share `SPEC/` + `conformance/`
- First-class roots: `python/` (host), `rust/` (peer crate), `demos/` (examples only)
- Removed ambiguous `peers/` nesting for production code
- Added `ARCHITECTURE.md`

---

## 2026-08-10 — documentation completeness + structure

### Added
- `TERMINOLOGY.md` — glossary (is / does / is-not / where) for all core terms
- `HOW_IT_WORKS.md` — human walkthrough with mermaid flows and algorithms
- `REFERENCE.md` — HTTP API, curl recipes, module map, how to add an action
- `FAQ.md` — short answers to common confusions
- `OPERATIONAL.md` — secrets, env, health honesty, production checklist
- `STRUCTURE.md` — permanent vs moving
- `SPEC/INVARIANTS.md` — testable laws + kill criteria
- `verify.sh` — one-command green (`--http` for live peer)

### Changed
- `uxc_peer` fail-closed secrets (`UXC_ALLOW_ORACLE_SECRET` for demo)
- HTTP `401` for `error.code == unauthorized`
- Health honesty: `formats` vs `codecs`, `demo_mode`, `once_jti_enforced: false`
- Morph **and** toast HTML-escape free-form strings; `signal_set` stays raw
- Cross-links across README, SPEC, conformance, peers

### Fixed
- Corrupted `escape_html` entities (compile break in action tests)

---

## 2026-08-10 — complete wire-native tree sync

### Added / restored (byte-faithful upload)
- Rust peer: types, wire_json, cap, cxb, op_tags, peer, actions
- Bins: `uxc_check`, `uxc_peer`
- Conformance JSON vectors + 14 CXB expected blobs + harnesses
- Python forward adapter
- SPEC drafts, PUBLIC_API_FREEZE, planning notes

### Status at that point
- Cap verify + CXB decode green
- HTTP action JSON-only
- once/jti and HTTP CXB negotiation still gaps

---

## Known open gaps (all versions until closed)

| Gap | Notes |
|-----|--------|
| once/jti consumption | SPEC required; not enforced in Cap 0.1 |
| HTTP Accept `+cxb` | Library codec only |
| Byte-identical CXB freeform encode | Structural re-encode only |
| WASM / mesh | Roadmap only |
