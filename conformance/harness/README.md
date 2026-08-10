# Second-language harness notes

**Goal:** Any peer can prove conformance without reading Python source.

## Minimal verification interface

A conforming implementation must expose (or be wrapable as) the following:

```text
decode_json(bytes) -> dict
encode_json(dict) -> bytes

# optional but required for full Phase 1
decode_cxb(bytes) -> dict
encode_cxb(dict) -> bytes

# capability (oracle tokens)
verify_cap(token: str, action: str, sealed_args: dict, *, max_age: int) -> dict | error
```

## Harnesses in this tree

| Script | Role | Deps |
|--------|------|------|
| `validate_json_vectors.py` | Structural Intent/Result/trace | stdlib only |
| `validate_cxb_expected.py` | Magic/len/sha256/CRC; re-encode when oracle importable | stdlib; optional `ux_channel` |
| `regenerate_cxb_expected.py` | Rebuild `expected/cxb/*` from pure-Python oracle | `ux_channel` on PYTHONPATH |

Rust peer: `cargo run --bin uxc_check -- ../../conformance`  
Optional live peer: `… --http http://127.0.0.1:8787`

## Suggested test loop (pseudocode)

```
for each vector in manifest.vectors.intent + result:
    doc = load_json(vector.file)
    round = decode_json(encode_json(doc))
    assert deep_equal_canonical(round, doc)

for each optional trace vector:
    # presence of trace must not break decode; absence must still be valid
    ...

for each cap case with concrete tokens:
    assert verify behaviour matches expected error or success

for each expected/cxb blob:
    assert is_cxb(blob) and crc_ok(blob)
    assert decode_cxb(blob) preserves action/ok from source JSON
```

## Canonicalization rules (for deep_equal)

- Object keys compared without order dependence
- Numbers: prefer exact integer match; floats compared with small epsilon only if needed
- Absent optional fields (`trace`, `meta` sub-keys) are equivalent to missing
- Unknown top-level fields on Intent must survive a round-trip or be explicitly stripped by a documented “strict” mode (default = preserve/ignore on read)

## CXB expected blobs

1. Produced by pure-Python `encode_cxb_python` from each Intent/Result/trace JSON vector
2. Stored under `expected/cxb/` with SHA-256 in `index.json` + `*.meta.json`
3. Second implementations must **decode** to the same logical dict; encode sha256 match is best-effort until freeform map key order is aligned

## Status

- [x] Interface and loop defined
- [x] Python structural harness green
- [x] Cap oracle token + Rust verify
- [x] CXB expected blobs + Python + Rust checks
- [x] Rust peer `uxc_check` loads the full suite

## Package entry

From repo root: `./verify.sh` (and `./verify.sh --http`).
See also [`../../REFERENCE.md`](../../REFERENCE.md), [`../../TERMINOLOGY.md`](../../TERMINOLOGY.md).
