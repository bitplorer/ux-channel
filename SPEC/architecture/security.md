# Security model

## Authority edges (only three)

| Edge | Authorizes | Does not authorize |
|------|------------|-------------------|
| **Cap** | Running this `action` with these sealed args | Session identity alone |
| **Bearer** (session) | Who is speaking | Money/delete actions without Cap when require_cap |
| **Proof** | Applying this Result’s `ops` on the peer | Host handler execution |

## Fail-closed table

| Condition | MUST behavior | Vector |
|-----------|---------------|--------|
| Missing Cap when required | No handler; `ok: false` unauthorized | `cap/missing` |
| Invalid / expired Cap | No handler | `cap/invalid` |
| args_hash mismatch | No handler | `cap/args-mismatch` |
| present Cap on open action, invalid | No handler (present-cap-must-verify) | `cap/present-bogus` |
| once Cap, jti already consumed | No handler | `cap/once-replay` |
| once Cap, nonce store unavailable | No handler | `cap/store-down` |
| Proof required, verify fails | Apply **zero** ops | `proof/reject` |
| Budget exceeded | Reject Result / do not apply | `apply/budget` |
| Oracle/demo secret in prod | Runtime MUST refuse to serve | runtime health |

## Key separation

- **Cap secret** ≠ **proof signing key** ≠ **TLS** material.  
- Rotation: Cap supports previous secrets window; proof uses `kid`.

## Assumptions (documented)

1. Transport integrity (TLS or equivalent) is provided by the environment.  
2. HTML encoding of user data in morph regions is the **app’s** responsibility; drivers MAY offer sanitizer hooks but Cap does not sanitize HTML.  
3. Stolen session bearer can submit Intents the user could submit; Caps and once reduce replay and arg tampering, they do not replace step-up auth for high risk.

## Non-goals for this document

XSS-proof morph by protocol alone; CRDT authorization; peer-minted Caps.
