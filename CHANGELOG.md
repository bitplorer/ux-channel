# Changelog — ux-channel wire-native package

History of **this** repository tree (`bitplorer/ux-channel`), not the full PyPI host package.

Format: newest first. “Law” vs “demo” follows [STRUCTURE.md](STRUCTURE.md).

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
