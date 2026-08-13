# Concurrency

## Laws (MUST)

1. once/jti consume is atomic and before side effects (or same transaction).  
2. Idempotency-Key / request_id dedupe is **separate** from once.  
3. Peer applies one Result at a time per session (single-flight).  
4. revoke → session gen++; peer cancels timers; proofs for old gen invalid.  

## Vectors

- `concurrency/once-double`  
- `concurrency/apply-serial`  

## Assumptions

- Multi-instance hosts share nonce and idempotency stores.  
- In-memory nonce is not safe across processes.
