# UX-Channel Protocol Specs (normative drafts)

**Status:** living drafts for Phase 0 / 1 / 1.5  
**IR version label:** `1` (field `"v": "1"`)  
**Goal:** a stranger can implement a peer without reading Python source.

| Document | Role | Stability |
|----------|------|-----------|
| [intent-result-ops.md](intent-result-ops.md) | Core IR: Intent, Result, ops vocabulary | **Normative target for 0.1** |
| [capability.md](capability.md) | Portable authority tokens | **Normative target for 0.1** |
| [INVARIANTS.md](INVARIANTS.md) | Testable laws + kill criteria | **Normative** |
| [BREAKING_CHANGE_POLICY.md](BREAKING_CHANGE_POLICY.md) | Major vs additive process | **Normative process** |
| [../STRUCTURE.md](../STRUCTURE.md) | Permanent vs moving (maintenance) | Process |
| [../OPERATIONAL.md](../OPERATIONAL.md) | Secrets, env, HTTP honesty | Operators |
| [../TERMINOLOGY.md](../TERMINOLOGY.md) | Glossary (is / does / is-not) | Guide |
| [../HOW_IT_WORKS.md](../HOW_IT_WORKS.md) | Human walkthrough (diagrams) | Guide |
| [../REFERENCE.md](../REFERENCE.md) | HTTP API + recipes | Guide |
| [../FAQ.md](../FAQ.md) | Short Q&A | Guide |
| [architecture/](architecture/) | EffectGraph, project, proofs, flow correlation, peer kernel | Additive; classic floor stays |
| Package `docs/core/CXB.md` | Binary wire format (CXB1 / CXBZ) | Normative inside 0.1.0 package |
| Package `docs/core/WIRE.md` | Multi-format wire surface | Supporting |

## Rules for all specs

1. JSON is the floor. Every required field must round-trip through `application/ux-channel+json`.
2. Optional envelopes (trace, surface hello, delta ops, receipt) must never be required for basic interop.
3. Field tags / dense keys in CXB are append-only; never reuse.
4. Caps authorize; transports only deliver.
5. Breaking changes require a new major IR version and a clear migration window (see BREAKING_CHANGE_POLICY.md).

## Conformance

Golden vectors + manifest + harness notes live under `../conformance/`.  
They are the executable source of truth for interop.

- JSON structural: `conformance/harness/validate_json_vectors.py`
- CXB expected: `conformance/expected/cxb/` + `validate_cxb_expected.py`
- Second implementation: `../rust` (`uxc_check` loads `manifest.json`, verifies JSON + cap oracle + CXB)

## Cap wire (Cap 0.1)

Portable encoding used by Python `CapService` and the Rust peer:

- `itsdangerous.URLSafeTimedSerializer` with salt `ux-channel-cap`
- django-concat key derivation + HMAC-SHA1
- `args_hash = sha256(json.dumps(args, sort_keys=True, separators=(',', ':'), default=str))[:32 hex]`
- Oracle: `conformance/vectors/cap/02-oracle-token.json`
- **once/jti:** required and **enforced** — Python `CapService.verify` + Rust `mint_once` / `MemoryNonceStore` (health `once_jti_enforced: true`)

## CXB

CXB encode/decode is implemented in the Rust peer and frozen under `conformance/expected/cxb/` (14 blobs).  
HTTP Accept negotiation for `application/ux-channel+cxb` is **not** on the wire yet (library codec only).

## Current next work

- HTTP Accept negotiation for `application/ux-channel+cxb` on the Rust peer
- Byte-identical freeform encode alignment (msgpack key order)
- Integrate ASGI forward into the full 0.1.0 package host
- P3: surface hello runtime + UDS
