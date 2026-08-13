# Cap vector 03 — once/jti (implemented)

**Law:** `once=true` requires `jti`. Verify consumes `cap:{jti}` atomically
**before** the handler. Missing store or missing jti → refuse. Replay → unauthorized.

**Python:** `CapService.mint(..., once=True)` + `verify(..., consume_once=True)`.
Inspect without burning: `consume_once=False`.

**Rust:** `CapService::mint_once` + `verify` (default consume). Inspect:
`verify_inspect`. `Peer::new` installs `MemoryNonceStore`.

**Redis:** `RedisNonceStore.use_once` is `SET key 1 NX EX ttl`. Connection
failure returns False (fail closed).

**Vectors (executable in gate / cargo test, not frozen tokens):**

| Case | Expect |
|------|--------|
| mint once → verify → verify | second verify `unauthorized` / replay |
| mint once, no nonce store | verify refuses (`nonce_store` / `OnceStoreRequired`) |
| `consume_once=False` then verify | first consume still succeeds |
| present bogus cap on open action | unauthorized |

Do not treat CXB, flow_id, or effect proofs as capability substitutes.
