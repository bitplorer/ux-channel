# Capability extension (once/jti, present-cap, parity)

Extends existing Cap law. Aligns all Cap-verifying hosts/peers.

## present-cap-must-verify

**MUST:** If `intent.cap` is present, it MUST be verified even when the action is otherwise open (no Cap required).

**Vector:** `cap/present-bogus`

## once / jti

### Mint

When single-use is required:

```text
once: true
jti: <unique string>   # MUST be present if once is true
```

### Verify + consume

**MUST** order:

1. Verify signature, exp, action, args_hash, optional sub/scopes.  
2. If `once` is true:  
   - If no nonce store configured → **reject** (fail closed).  
   - If `jti` missing → **reject**.  
   - `use_once("cap:" + jti, ttl)` MUST be atomic; false → **reject** replay.  
3. Only then run handler (or same DB transaction as side effects).

**MUST NOT:** check jti after handler side effects without transactional pairing.

**Vectors:** `cap/once-replay`, `cap/store-down`

## args_hash

Canonical form **MUST** be: UTF-8 JSON with sorted keys, separators `(',', ':')`, then SHA-256 hex truncated to 32 characters (existing parity).

**Vector:** existing `conformance/vectors/cap` plus language parity tests.

## Config assumptions

- Production deployments that mint `once=true` Caps **MUST** configure a durable nonce store (e.g. Redis).  
- In-memory store is **only** for single-process demo/tests; document as non-durable.
