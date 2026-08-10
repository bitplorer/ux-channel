# UX-Channel Protocol Specs (normative drafts)

**Status:** living drafts for Phase 0 / 1 / 1.5  
**IR version label:** `1` (field `"v": "1"`)  
**Goal:** a stranger can implement a peer without reading Python source.

| Document | Role | Stability |
|----------|------|-----------|
| [intent-result-ops.md](intent-result-ops.md) | Core IR: Intent, Result, ops vocabulary | **Normative target for 0.1** |
| [capability.md](capability.md) | Portable authority tokens | **Normative target for 0.1** |
| [BREAKING_CHANGE_POLICY.md](BREAKING_CHANGE_POLICY.md) | What may change inside a major vs what requires a new major | **Normative process** |
| [../ux-channel-design-causal-surface.md](../ux-channel-design-causal-surface.md) | Optional envelopes: causal spine, surface negotiation, deltas | Phase 1.5 (additive) |
| Package `docs/core/CXB.md` | Binary wire format (CXB1 / CXBZ) | Already treated as normative inside 0.1.0 |
| Package `docs/core/WIRE.md` | Multi-format wire surface (JSON floor + opt-in) | Supporting |

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
- Second implementation: `../peers/ux_channel_rs` (`uxc_check` loads `manifest.json`, verifies JSON + cap oracle + CXB)

## Cap wire (implementation note, Cap 0.1)

Until CXB work lands, the portable cap encoding used by Python `CapabilityService` and the Rust peer is:

- `itsdangerous.URLSafeTimedSerializer` with salt `ux-channel-cap`
- django-concat key derivation + HMAC-SHA1
- `args_hash = sha256(json.dumps(args, sort_keys=True, separators=(',', ':'), default=str))[:32 hex]`
- Oracle: `conformance/vectors/cap/02-oracle-token.json`

## Current next work

- HTTP Accept negotiation for `application/ux-channel+cxb` on the Rust peer
- Byte-identical freeform encode alignment (msgpack key order)
- Integrate ASGI forward into the full 0.1.0 package host
- P3: surface hello runtime + UDS
