# AGENTS.md — ux-channel wire-native

Orientation for agents continuing this package.

Read [MENTAL_MODEL.md](MENTAL_MODEL.md) then [python/STABILITY.md](python/STABILITY.md) then **[AUTOMATION.md](AUTOMATION.md)**.

**Humans reading the tree:** [`TERMINOLOGY.md`](TERMINOLOGY.md) → [`HOW_IT_WORKS.md`](HOW_IT_WORKS.md) → [`REFERENCE.md`](REFERENCE.md) → [`FAQ.md`](FAQ.md). Do not assume IR/cap/CXB vocabulary is known.

## North star

```text
Any peer  ── Intent { action, args, cap } ──▶  Any peer
Any peer  ◀── Result { ok, ops[], error } ──  Any peer
```

One IR. JSON floor. Caps authorize. Transports only deliver. Peers > FFI.

## Automation first (ceremonial code)

**Do not hand-edit derived / boring inventories.** Default to generators:

| Need | Command |
|------|---------|
| Refresh catalog + derived map fields | `make regen` |
| Inventory packages from disk | `make sync-map` |
| Full green | `make verify` |
| CXB expected blobs | `make cxb-regen` |

Never hand-edit `catalog/catalog.json` or `PACKAGE_MAP.json` → `modules` / `module_count`.  
Package `__init__.py` export lists **are** hand design (public API).  
Policy details: [AUTOMATION.md](AUTOMATION.md).

## Non-negotiables

1. Do not invent a parallel RPC style.
2. Do not require CXB, trace, or surface-hello for basic interop.
3. Cap tags / CXB field tags are append-only (see `SPEC/BREAKING_CHANGE_POLICY.md`).
4. Keep the public Python surface frozen (`PUBLIC_API_FREEZE.md`) when integrating the full package.
5. Prefer durable contract work over feature sprawl.
6. Read `STRUCTURE.md` before changing code (permanent vs moving).
6b. Read `ARCHITECTURE.md` for monorepo package boundaries (`python/`, `rust/`, law).
7. Read `OPERATIONAL.md` before suggesting `cargo run --bin uxc_peer`.
8. Do not leave recovery docs pointing at dead sandbox paths — GitHub `main` is truth.

## Verify before claiming green

Do **not** ask humans to re-run ceremonial steps by hand — use automation:

```bash
make verify          # preferred (health + law + Python + Rust)
make verify-http     # + live peer + demo forward
# equivalents:
./verify.sh
./verify.sh --http
```

CI runs the same on every push (`.github/workflows/ci.yml`).

## Intentional policies (not bugs)

| Policy | Behavior |
|--------|----------|
| Cap required | `Cart.add` always needs a valid cap |
| Present-cap-must-verify | Any Intent with `cap` set is verified, even for open actions (health: `present_cap_must_verify`) |
| HTTP formats | `/ux-channel/action` is JSON only; health lists library `codecs` separately |
| Arg types | Integer fields (`qty`, `by`) reject non-integers (no silent coercion) |
| Morph / toast display | Free-form strings HTML-escaped |
| signal_set | Raw semantic values (not escaped) — intentional |
| Oracle secret | Public; `uxc_peer` refuses it unless `UXC_ALLOW_ORACLE_SECRET=1` |
| once/jti | SPEC requires; Rust Cap 0.1 does not enforce yet (`once_jti_enforced: false`) — do not claim green |
| HTTP status | 200 / 401 unauthorized / 400 other Result errors / 500 encode failure — body still rules |

## Where to change things

| Need | Path |
|------|------|
| IR types | `rust/src/types.rs` |
| Cap crypto | `rust/src/cap.rs` |
| CXB | `rust/src/cxb.rs` |
| Dispatch | `rust/src/actions.rs` + `peer.rs` |
| HTTP surface | `rust/src/bin/uxc_peer.rs` |
| Conformance | `conformance/` |
| Invariants / structure | `SPEC/INVARIANTS.md`, `STRUCTURE.md` |
| Glossary (is / does / not) | `TERMINOLOGY.md` |
| Human story / diagrams | `HOW_IT_WORKS.md` |
| HTTP API / recipes | `REFERENCE.md` |
| FAQ | `FAQ.md` |
| Operators | `OPERATIONAL.md` |
| Automation policy | `AUTOMATION.md` |
| Roadmap next steps | `ux-channel-roadmap.md` |
| Full Python host library | `python/src/ux_channel/` (see `python/README.md`) |
| Python concept map (regions, …) | `python/ONTOLOGY.md` |
| Python host permanence | `python/STRUCTURE.md` |
| Python application imports | `ux_channel.api` |
| Thin Python→Rust forward | `demos/python_forward/` |
| Design / arch overviews | package `__init__.py` + `PACKAGE_MAP` `package_docs` + `ARCHITECTURE.md` |
