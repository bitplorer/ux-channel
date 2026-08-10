# Breaking Change Policy — IR & Caps

**Applies to:** Intent / Result / ops IR, capability tokens, CXB dense tags, public media types.

## Definitions

| Kind | Meaning | Example |
|------|---------|---------|
| **Major** | Existing correct peers can break | Removing a required field, changing meaning of `ok`, reusing a CXB dense tag, changing args_hash algorithm |
| **Minor / additive** | Old peers keep working | New optional field, new op type (free string), new optional envelope (`trace`) |
| **Patch** | Bugfix, docs, clearer errors | Fixing a mis-documented error code, adding a vector |

## Hard rules

1. **`"v": "1"`** stays until a deliberate major bump. A new major gets `"v": "2"` and a migration window.
2. **CXB dense tags 1–63** are append-only. Never reuse a tag number.
3. **Required fields** on Intent / Result may not be removed or repurposed inside a major.
4. **Error codes** that appear in golden vectors (`unauthorized`, `validation`, …) are stable within a major.
5. **Capability** canonical payload fields used for verification (action, args_hash, iat, sub, scopes, jti, once) are stable within a major. New optional claims are fine.
6. **JSON floor** always works. New formats or envelopes are opt-in.

## Process for a major

1. Write the migration notes and dual-run period.
2. Ship vectors for both old and new majors during the window.
3. Only then drop the old major from the primary conformance suite.

## What does *not* require a major

- New op types (string names)
- Optional Result fields (`trace`, future `receipt`, …)
- New surface dialects advertised in handshake
- Additional media types that negotiate alongside JSON/CXB
- Performance or encoding improvements that preserve the dict IR

## Ownership

The SPEC documents under `SPEC/` plus the golden vectors under `conformance/` are the source of truth. Implementation code is secondary.
