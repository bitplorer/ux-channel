# Conformance vectors — ux-channel IR 0.1

**Purpose:** Language-agnostic golden files so any peer (Python, Rust, WASM, …) can prove it speaks the same Intent / Result / ops / cap contract.

## Layout

```text
conformance/
  README.md
  manifest.json                 ← machine-readable index of all vectors
  vectors/
    intent/                     ← Intent documents (JSON)
    result/                     ← Result documents (JSON)
    cap/                        ← capability notes + oracle token
    trace/                      ← optional causal spine (Phase 1.5)
    handshake/                  ← optional surface hello
  expected/cxb/                 ← frozen CXB1 blobs + sha256 from pure-Python oracle
  harness/
    validate_json_vectors.py    ← structural JSON (no package deps)
    validate_cxb_expected.py    ← CXB sha/CRC (+ oracle re-encode when available)
    regenerate_cxb_expected.py  ← rebuild expected/cxb from oracle
    README.md                   ← second-language verification interface
```

## Rules for every vector

1. JSON is the source of truth. CXB binaries are derived and must decode to the same dict.
2. Filenames are stable: `NN-short-name.json`.
3. Each JSON file is a single value (object). No comments inside the JSON.
4. `manifest.json` lists every vector, its kind (positive/negative/notes), and notes.
5. Failure cases are first-class.

## Current coverage

| Category | Vectors present |
|----------|-----------------|
| Intent   | minimal, request_id, cap placeholder, unknown-fields-ignored |
| Result   | ok+morph, ok+toast, unauthorized, validation+fields, navigate, signal+noop, multi-ops |
| Cap      | notes + oracle token (`02-oracle-token.json`) |
| Trace    | single-hop, multi-hop, missing-trace-still-valid |
| Handshake | surface-hello (optional Phase 1.5+) |
| CXB      | 14 frozen blobs under `expected/cxb/` |

### Vector catalog (files)

| Path | Proves |
|------|--------|
| `vectors/intent/01-minimal.json` | Smallest valid Intent |
| `vectors/intent/02-with-request-id.json` | `request_id` present |
| `vectors/intent/03-with-cap-placeholder.json` | Cap field shape |
| `vectors/intent/04-unknown-fields-ignored.json` | Forward-compatible ignore |
| `vectors/result/01-ok-morph.json` | Success + morph op |
| `vectors/result/02-ok-toast.json` | Success + toast op |
| `vectors/result/03-error-unauthorized.json` | Stable `unauthorized` |
| `vectors/result/04-error-validation.json` | Stable `validation` + fields |
| `vectors/result/05-ok-navigate-safe.json` | navigate op |
| `vectors/result/06-ok-signal-and-noop.json` | signal_set + noop |
| `vectors/result/07-ok-multi-ops.json` | Multiple ops ordered |
| `vectors/cap/02-oracle-token.json` | Concrete token + hash algorithm |
| `vectors/trace/01-single-hop.json` | Optional trace |
| `vectors/trace/02-multi-hop.json` | Multi-hop trace |
| `vectors/trace/03-missing-trace-still-valid.json` | No trace still valid |
| `vectors/handshake/01-surface-hello.json` | Surface advertisement sketch |
| `expected/cxb/*` (14) | CXB decode oracle freeze |

Machine index: [`manifest.json`](manifest.json). Full HTTP recipes: [`../REFERENCE.md`](../REFERENCE.md).

## Phase 1 exit criteria

- [x] Seed positive Intent/Result vectors
- [x] Unknown fields ignored case
- [x] Stable error codes for unauthorized & validation
- [x] Optional trace examples + “missing trace still valid”
- [x] Manifest + harness interface described
- [x] Concrete cap oracle token
- [x] CXB expected blobs under `expected/cxb/`
- [x] Second-language peer loads the suite (`rust` `uxc_check`)

## How to run

```bash
python3 conformance/harness/validate_json_vectors.py
python3 conformance/harness/validate_cxb_expected.py   # oracle if PYTHONPATH set
cd rust && cargo run --bin uxc_check -- ../../conformance
```

## Related

- [`../TERMINOLOGY.md`](../TERMINOLOGY.md) — glossary
- [`../HOW_IT_WORKS.md`](../HOW_IT_WORKS.md) — human walkthrough
- [`../REFERENCE.md`](../REFERENCE.md) — HTTP + vector recipes
- [`../FAQ.md`](../FAQ.md) — short Q&A
- [`../SPEC/intent-result-ops.md`](../SPEC/intent-result-ops.md)
- [`../SPEC/capability.md`](../SPEC/capability.md)
- [`../SPEC/INVARIANTS.md`](../SPEC/INVARIANTS.md)
- [`../SPEC/BREAKING_CHANGE_POLICY.md`](../SPEC/BREAKING_CHANGE_POLICY.md)
- Package `docs/core/CXB.md` (inside 0.1.0 zip)
